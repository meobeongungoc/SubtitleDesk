from __future__ import annotations

import json
import os
import queue
import re
import threading
import time
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

from . import __version__
from .bridge import validate_message
from .core import (Movie, MAX_ARCHIVE, SUB_EXTENSIONS, decode_subtitle, match_score,
                   parse_movie, save_subtitle, unpack_subtitles)
from .providers import Context, Query, SearchEngine, load_registry
from .storage import CredentialError, SecretStore, load_settings, write_json
from .players import ADAPTERS, launch
from .sources import error_text
from .themes import ThemeManager, THEMES


class Application:
    def __init__(self, home: Path, hidden=False):
        self.home = home
        self.data = home / "data"
        self.data.mkdir(exist_ok=True)
        # Python 3.13's venv may miss the base installation's Tcl script path.
        # Scope the workaround to this process; frozen bundles set their own paths.
        if not getattr(sys, "frozen", False):
            for variable, folder in (("TCL_LIBRARY", "tcl8.6"), ("TK_LIBRARY", "tk8.6")):
                location = Path(sys.base_prefix) / "tcl" / folder
                if location.is_dir():
                    os.environ.setdefault(variable, str(location))
        try:
            from tkinterdnd2 import TkinterDnD, DND_FILES
            class DropRoot(tk.Tk, TkinterDnD.DnDWrapper):
                pass
            self.root = DropRoot()
            if hidden:
                self.root.withdraw()
            # tkdnd can process idle events while loading. Hide before loading it.
            TkinterDnD.require(self.root)
            self.dnd_type = DND_FILES
        except ImportError:
            self.root = tk.Tk()
            self.dnd_type = None
        if hidden:
            self.root.withdraw()
        self.root.title(f"SubtitleDesk {__version__}")
        self.root.minsize(1000, 600)
        self.settings_ok = True
        self.startup_notice = ""
        try:
            self.settings = load_settings(self.data)
        except ValueError as exc:
            from .storage import DEFAULTS
            self.settings = DEFAULTS.copy()
            self.settings_ok = False
            self.startup_notice = str(exc)
        geometry = self.settings["geometry"]
        self.root.geometry(geometry if re.fullmatch(r"\d+x\d+(?:[+-]\d+){0,2}", geometry) else "1080x780")
        self.secrets = SecretStore(self.data)
        self.registry = load_registry(self.secrets)
        self.engine = SearchEngine(self.registry)
        self.events = queue.Queue()
        self.search_cancel = threading.Event()
        self.download_cancel = threading.Event()
        self.search_id = 0
        self.busy = False
        self.downloading = False
        self.download_id = 0
        self.download_slots = threading.BoundedSemaphore(2)
        self.results = {}
        self.candidates = []
        self.selected_data = None
        self.selected_name = ""
        self.saved_path = ""
        self.browser_pending = []
        self.vars = {name: tk.StringVar() for name in
                     ("movie", "title", "year", "season", "episode", "release", "url")}
        self.language = tk.StringVar(value=self.settings["languages"])
        self.player_kind = tk.StringVar(value=self.settings["player_kind"])
        self.player_path = tk.StringVar(value=self.settings["player_path"])
        self.output_dir = tk.StringVar(value=self.settings["output_dir"])
        self.beside = tk.BooleanVar(value=self.settings["save_beside"])
        self.encoding = tk.StringVar(value="auto")
        self.status = tk.StringVar(value=self.startup_notice or "Ready — choose a folder or import subtitles.")
        self.build_ui()
        from .simple_ui import SimpleLibraryUI
        self.library = SimpleLibraryUI(self)
        self.theme_manager.apply(self.theme_key)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(120, self.poll)

    def build_ui(self):
        self.theme_manager = ThemeManager(self.root)
        self.settings.pop('background_blur', None)
        self.theme_key = self.theme_manager.apply(self.settings.get('theme', 'blue'))
        self.theme_manager.set_font(self.settings.get('font_family', 'Segoe UI'))
        self.theme_manager.set_glass(self.settings.get('glass_strength', 10))
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)
        self.pages = ttk.Notebook(outer)
        self.pages.pack(fill="both", expand=True)
        self.main_content = ttk.Frame(self.pages)
        self.workflow = ttk.Frame(self.main_content, padding=12)
        self.vocabulary_page = ttk.Frame(self.pages)
        self.tools_window = ttk.Frame(self.pages)
        self.appearance_window = ttk.Frame(self.pages)
        for frame, label in ((self.main_content, "Library"), (self.vocabulary_page, "Vocabulary"), (self.tools_window, "Settings"),
                             (self.appearance_window, "Appearance")):
            self.pages.add(frame, text=label)
        self.editor_page = ttk.Frame(self.pages, padding=12)
        self.pages.bind("<<NotebookTabChanged>>", self.page_changed)
        self.confirmation = ttk.Frame(outer, padding=(0, 6))
        self.pending_confirmation = None
        appearance_body = ttk.Frame(self.appearance_window, padding=22)
        appearance_body.pack(fill="both", expand=True)
        appearance = ttk.Frame(appearance_body)
        appearance.pack(fill='x', pady=(0,18))
        ttk.Label(appearance, text='Theme', style='Hint.TLabel').pack(side='left', padx=(0,8))
        self.theme_label = tk.StringVar(value=THEMES[self.theme_key][0])
        self.theme_picker = ttk.Combobox(appearance, textvariable=self.theme_label,
            values=[p[0] for p in THEMES.values()], state='readonly', width=29)
        self.theme_picker.pack(side='left')
        self.theme_picker.bind('<<ComboboxSelected>>', self.change_theme)
        glass_row = ttk.Frame(appearance_body)
        glass_row.pack(fill='x', pady=(0,8))
        ttk.Label(glass_row, text='Transparency', style='Hint.TLabel').pack(side='left', padx=(0,8))
        self.glass_value = tk.IntVar(value=self.theme_manager.glass_strength)
        self.glass_readout = tk.StringVar()
        self.glass_scale = tk.Scale(glass_row, from_=0, to=100, resolution=5, orient='horizontal',
            variable=self.glass_value, command=self.change_glass, showvalue=False, length=180,
            sliderlength=18, width=8, borderwidth=0, highlightthickness=0)
        self.glass_scale.pack(side='left')
        ttk.Label(glass_row, textvariable=self.glass_readout, style='Hint.TLabel').pack(side='left', padx=10)
        self.glass_readout.set(f'{self.theme_manager.glass_strength}%')
        self.glass_save_timer = None
        font_row = ttk.Frame(appearance_body)
        font_row.pack(fill='x', pady=18)
        ttk.Label(font_row, text='Font', style='Hint.TLabel').pack(side='left', padx=(0,12))
        self.font_choice = tk.StringVar(value=self.theme_manager.font_family)
        self.font_picker = ttk.Combobox(font_row, textvariable=self.font_choice,
            values=self.theme_manager.font_families, width=24)
        self.font_picker.pack(side='left')
        self.font_picker.bind('<<ComboboxSelected>>', self.change_font)
        self.font_picker.bind('<Return>', self.change_font)
        self.font_picker.bind('<Escape>', lambda e: self.font_choice.set(self.theme_manager.font_family))
        self.font_picker.bind('<KeyRelease>', self.filter_fonts)
        ttk.Label(appearance_body, text="Changes are saved automatically.\nTransparency affects the entire window. Choose any installed font and one of the four themes.",
                  style="Hint.TLabel", wraplength=650).pack(anchor="w", pady=(6, 0))
        notebook = ttk.Notebook(self.tools_window)
        notebook.pack(fill="both", expand=True)
        self.sources = ttk.Frame(notebook, padding=12)
        self.preferences = ttk.Frame(notebook, padding=12)
        notebook.add(self.sources, text="Sources")
        notebook.add(self.preferences, text="Player & browser")
        self.notebook = notebook
        ttk.Button(self.workflow, text="Back to movie library", command=self.show_library).pack(anchor="w", pady=(0, 8))
        movie_row = ttk.Frame(self.workflow)
        movie_row.pack(fill="x")
        ttk.Label(movie_row, text="Video file", width=12).pack(side="left")
        movie_entry = ttk.Entry(movie_row, textvariable=self.vars["movie"])
        movie_entry.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(movie_row, text="Choose video…", command=self.choose_movie).pack(side="left")
        if self.dnd_type:
            self.root.drop_target_register(self.dnd_type)
            self.root.dnd_bind("<<Drop>>", self.drop)
        ttk.Label(self.workflow, text="Drop a video, subtitle or ZIP file into the window.",
                  style="Hint.TLabel").pack(anchor="w", pady=(4, 8))
        fields = ttk.Frame(self.workflow)
        fields.pack(fill="x")
        for col, (label, key, width) in enumerate((
            ("Title", "title", 38), ("Year", "year", 7),
            ("Season", "season", 6), ("Episode", "episode", 6), ("Release", "release", 24)
        )):
            ttk.Label(fields, text=label).grid(row=0, column=col, sticky="w")
            entry = ttk.Entry(fields, textvariable=self.vars[key], width=width)
            entry.grid(row=1, column=col, sticky="ew", padx=(0, 8))
            fields.columnconfigure(col, weight=3 if key == "title" else 1)
        url_row = ttk.Frame(self.workflow)
        url_row.pack(fill="x", pady=8)
        ttk.Label(url_row, text="Page URL", width=12).pack(side="left")
        ttk.Entry(url_row, textvariable=self.vars["url"]).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(url_row, text="Parse filename", command=self.parse_input).pack(side="left")
        controls = ttk.Frame(self.workflow)
        controls.pack(fill="x", pady=(0, 8))
        self.search_button = ttk.Button(controls, text="Find subtitles", command=self.search)
        self.search_button.pack(side="left")
        ttk.Button(controls, text="Cancel", command=self.cancel).pack(side="left", padx=6)
        ttk.Button(controls, text="Import subtitle / ZIP…", command=self.import_dialog).pack(side="left")
        self.receive_button = ttk.Button(controls, text="Receive from browser (0)", command=self.take_browser)
        self.receive_button.pack(side="left", padx=6)
        self.source_note = ttk.Label(controls, text="No subtitle sources configured",
                                     style="Hint.TLabel")
        self.source_note.pack(side="left", padx=12)
        table_frame = ttk.Frame(self.workflow)
        table_frame.pack(fill="both", expand=True)
        columns = ("source", "lang", "release", "author", "quality", "score")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", height=5,
                                  selectmode="browse")
        for key, title, width in zip(columns,
                                    ("Source", "Languages", "Release / name", "Uploader", "Quality", "Match"),
                                    (100, 70, 320, 100, 110, 55)):
            self.table.heading(key, text=title)
            self.table.column(key, width=width, minwidth=40)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.table.bind("<<TreeviewSelect>>", self.result_selected)
        self.reason = tk.StringVar(value="Match scores are suggestions, not a guarantee of synchronization.")
        ttk.Label(self.workflow, textvariable=self.reason, style="Hint.TLabel",
                  wraplength=900).pack(anchor="w", pady=5)
        file_row = ttk.Frame(self.workflow)
        file_row.pack(fill="x")
        ttk.Button(file_row, text="Download selected result", command=self.download).pack(side="left")
        self.candidate = ttk.Combobox(file_row, state="readonly", width=48)
        self.candidate.pack(side="left", padx=8, fill="x", expand=True)
        self.candidate.bind("<<ComboboxSelected>>", self.show_candidate)
        ttk.Label(file_row, text="Encoding").pack(side="left")
        combo = ttk.Combobox(file_row, textvariable=self.encoding, state="readonly",
                             values=("auto", "utf-8-sig", "utf-16", "cp1258", "cp1252"), width=12)
        combo.pack(side="left", padx=(4, 0))
        combo.bind("<<ComboboxSelected>>", self.show_candidate)
        self.preview = ScrolledText(self.workflow, height=7, wrap="word", font=("Consolas", 10))
        self.preview.pack(fill="both", expand=True, pady=8)
        self.preview.configure(state="disabled")
        actions = ttk.Frame(self.workflow)
        actions.pack(fill="x")
        ttk.Button(actions, text="Save subtitle…", command=self.save).pack(side="left")
        ttk.Button(actions, text="Save & open in player", command=self.save_and_open).pack(side="left", padx=8)
        self.saved_label = ttk.Label(actions, text="No subtitle saved", style="Hint.TLabel")
        self.saved_label.pack(side="left")
        self.build_sources()
        self.build_preferences()
        ttk.Label(outer, textvariable=self.status, style="Hint.TLabel", wraplength=1000).pack(side="bottom", anchor="w", pady=(10, 0), before=self.pages)

    def notify(self, text):
        self.status.set(text)

    def page_changed(self, event=None):
        if self.pages.select() == str(self.vocabulary_page) and hasattr(self, "library"):
            self.library.show_vocabulary()

    def show_appearance(self):
        self.pages.select(self.appearance_window)

    def show_tools(self, frame):
        if frame == self.workflow:
            self.library.btab.pack_forget()
            self.workflow.pack(fill="both", expand=True)
            self.pages.select(self.main_content)
        else:
            self.notebook.select(frame)
            self.pages.select(self.tools_window)

    def show_library(self):
        self.workflow.pack_forget()
        self.library.btab.pack(fill="both", expand=True)
        self.pages.select(self.main_content)

    def inline_editor(self, title):
        for child in self.editor_page.winfo_children():
            child.destroy()
        if str(self.editor_page) not in self.pages.tabs():
            self.pages.add(self.editor_page, text=title)
        else:
            self.pages.tab(self.editor_page, text=title)
        ttk.Button(self.editor_page, text="Back to Library", command=self.close_editor).pack(anchor="w", pady=(0, 12))
        self.pages.select(self.editor_page)
        return self.editor_page

    def close_editor(self):
        self.pages.select(self.main_content)
        if str(self.editor_page) in self.pages.tabs():
            self.pages.forget(self.editor_page)

    def confirm_inline(self, text, action, label="Confirm"):
        for child in self.confirmation.winfo_children():
            child.destroy()
        self.pending_confirmation = action
        ttk.Label(self.confirmation, text=text, wraplength=650).pack(side="left", fill="x", expand=True)
        ttk.Button(self.confirmation, text=label, command=self.accept_confirmation).pack(side="left", padx=6)
        ttk.Button(self.confirmation, text="Cancel", command=self.cancel_confirmation).pack(side="left")
        self.confirmation.pack(fill="x", before=self.pages)

    def accept_confirmation(self):
        action = self.pending_confirmation
        self.cancel_confirmation()
        if action:
            action()

    def cancel_confirmation(self):
        self.pending_confirmation = None
        self.confirmation.pack_forget()

    def scrollable(self, parent):
        canvas = tk.Canvas(parent, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = ttk.Frame(canvas, padding=8)
        item = canvas.create_window(0, 0, anchor="nw", window=body)
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(item, width=e.width))
        def wheel(event):
            target = event.widget
            if isinstance(target, (ttk.Combobox, ttk.Treeview, tk.Text)):
                return
            while target is not None:
                if target == body:
                    canvas.yview_scroll(-int(event.delta / 120), "units")
                    return "break"
                target = getattr(target, "master", None)
        self.root.bind("<MouseWheel>", wheel, add="+")
        return body

    def build_sources(self):
        content = self.scrollable(self.sources)
        ttk.Label(content, text="Your sources", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        self.enabled = {}
        if not self.registry.providers:
            ttk.Label(content, text="No subtitle sources configured\n\n"
                      "Import, preview, save and open local subtitles without an online source.\n"
                      "Additional providers can be added independently.\n"
                      "The application does not show sample search results.",
                      justify="left", style="Hint.TLabel").pack(anchor="w", pady=16)
        for key, provider in self.registry.providers.items():
            caps = provider.capabilities
            enabled = tk.BooleanVar(value=key not in self.settings["disabled_sources"])
            self.enabled[key] = enabled
            box = ttk.LabelFrame(content, text=caps.name, padding=10)
            box.pack(fill="x", pady=6)
            ttk.Checkbutton(box, text="Enable source", variable=enabled).pack(anchor="w")
            ttk.Label(box, text=f"{len(caps.languages)} supported languages • Timeout: {caps.timeout}s").pack(anchor="w")
            ttk.Label(box, text=("Get an API key at subdl.com/panel."
                                if key == "subdl" else
                                "API key: opensubtitles.com/consumers. Username/password are optional for account downloads."),
                      style="Hint.TLabel", wraplength=850).pack(anchor="w")
            for field in caps.credentials:
                row = ttk.Frame(box)
                row.pack(fill="x", pady=4)
                ttk.Label(row, text=field, width=18).pack(side="left")
                value = tk.StringVar()
                ttk.Entry(row, textvariable=value, show="•").pack(side="left", fill="x", expand=True)
                ttk.Button(row, text="Save", command=lambda k=key, f=field, v=value:
                           self.save_secret(k, f, v)).pack(side="left", padx=5)
                try:
                    stored = bool(self.secrets.get(key, field))
                    state = "Saved" if stored else "Not entered"
                except CredentialError as exc:
                    enabled.set(False)
                    state = "Unreadable"
                    self.startup_notice = str(exc)
                    self.status.set(str(exc))
                indicator = ttk.Label(row, text=state, width=12)
                indicator.pack(side="left")
                if not hasattr(self, "secret_indicators"):
                    self.secret_indicators = {}
                self.secret_indicators[(key, field)] = indicator
        ttk.Button(content, text="Archive unreadable credential storage & reset…",
                   command=lambda: self.confirm_inline(
                       "Archive the existing credential file and reset saved keys? The backup stays in the private data folder.",
                       self.reset_credentials, "Archive & reset")).pack(anchor="w", pady=6)
        if self.registry.providers:
            self.source_note.configure(text=f"{len(self.registry.providers)} available sources")

    def build_preferences(self):
        frame = self.scrollable(self.preferences)
        ttk.Label(frame, text="Settings", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))
        for label, variable, browse in (
            ("Preferred language codes, comma-separated", self.language, None),
            ("Player executable", self.player_path, self.choose_player),
            ("Subtitle output folder", self.output_dir, self.choose_output)
        ):
            ttk.Label(frame, text=label).pack(anchor="w", pady=(6, 2))
            row = ttk.Frame(frame)
            row.pack(fill="x")
            ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
            if browse:
                ttk.Button(row, text="Browse…", command=browse).pack(side="left", padx=5)
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=10)
        ttk.Label(row, text="Player").pack(side="left")
        ttk.Combobox(row, textvariable=self.player_kind, values=tuple(ADAPTERS),
                     state="readonly", width=20).pack(side="left", padx=10)
        ttk.Checkbutton(frame, text="Save next to the selected video",
                        variable=self.beside).pack(anchor="w")
        ttk.Label(frame, text="MPC-BE opens a video with /sub and may restart playback;\n"
                  "live subtitle injection is not supported. More players can use separate adapters.",
                  style="Hint.TLabel").pack(anchor="w", pady=8)
        ttk.Button(frame, text="Save settings", command=self.persist).pack(anchor="w")
        ttk.Button(frame, text="Import local subtitle / ZIP…", command=self.import_dialog).pack(anchor="w", pady=8)
        ttk.Separator(frame).pack(fill="x", pady=18)
        ttk.Label(frame, text="Browser connection", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(frame, text="One extension for Edge / Chrome; a separate package for Firefox.\n"
                  "See USER-GUIDE.md for installation and Native Messaging setup.\n"
                  "The bridge receives only the URL, title or text you explicitly select. Check the title before searching.\n"
                  "The app works independently without an extension.",
                  style="Hint.TLabel", justify="left").pack(anchor="w", pady=10)
        self.browser_note = tk.StringVar(value="No browser requests received.")
        ttk.Label(frame, textvariable=self.browser_note, wraplength=850).pack(anchor="w")
        ttk.Button(frame, text="Receive next browser request",
                   command=self.take_browser).pack(anchor="w", pady=8)

    def save_secret(self, key, field, variable):
        try:
            self.secrets.set(key, field, variable.get())
            self.secret_indicators[(key, field)].configure(text="Saved" if variable.get() else "Not entered")
            variable.set("")
            self.status.set("Saved with Windows DPAPI. Save an empty value to remove this field.")
        except CredentialError as exc:
            self.notify(str(exc))
        except Exception:
            self.notify("Could not save the Windows-protected credential.")

    def reset_credentials(self):
        try:
            self.secrets.reset()
            for indicator in self.secret_indicators.values():
                indicator.configure(text="Not entered")
            self.notify("Previous credential storage archived. Enter your keys and enable the sources you want.")
        except OSError:
            self.notify("Could not archive credential storage. No credentials were reset.")

    def set_movie(self, value):
        self.vars["movie"].set(value)
        self.apply_movie(parse_movie(value))
        self.saved_path = ""
        self.saved_label.configure(text="No subtitle saved for this video")

    def apply_movie(self, movie):
        for name in ("title", "year", "season", "episode", "release"):
            self.vars[name].set(getattr(movie, name))

    def parse_input(self):
        self.apply_movie(parse_movie(self.vars["movie"].get() or self.vars["title"].get()))

    def choose_movie(self):
        value = filedialog.askopenfilename(title="Choose video", filetypes=[
            ("Video", "*.mkv *.mp4 *.avi *.mov *.m4v *.webm *.wmv *.ts"), ("All files", "*.*")])
        if value:
            self.set_movie(value)

    def choose_player(self):
        value = filedialog.askopenfilename(title="Choose player", filetypes=[("Application", "*.exe")])
        if value:
            self.player_path.set(value)

    def choose_output(self):
        value = filedialog.askdirectory(title="Subtitle output folder")
        if value:
            self.output_dir.set(value)

    def drop(self, event):
        if self.library.batch_busy or self.library.library_refreshing:
            self.notify("Finish or cancel the current library task before dropping another file.")
            return event.action
        files = self.root.tk.splitlist(event.data)
        if len(files) != 1:
            self.notify("Drop one video or subtitle/ZIP file at a time.")
        elif Path(files[0]).is_dir():
            self.library.load_folder(files[0])
        elif Path(files[0]).suffix.lower() in SUB_EXTENSIONS | {".zip", ".rar", ".7z"}:
            self.import_file(files[0])
            self.show_tools(self.workflow)
        else:
            self.set_movie(files[0])
            from .batch import Episode, identify, existing_subtitle
            path = Path(files[0])
            if path.is_file():
                found = existing_subtitle(path)
                self.library.set_rows([Episode(path, identify(path), not bool(found),
                                               "Subtitle exists" if found else "Not searched")])
        return event.action

    def current_movie(self):
        for key in ("year", "season", "episode"):
            value = self.vars[key].get().strip()
            if value and not re.fullmatch(r"\d{1,4}", value):
                raise ValueError("Year, season and episode must be numbers or empty.")
        title = self.vars["title"].get().strip()
        if not title:
            raise ValueError("Enter a title before searching.")
        return Movie(*(self.vars[key].get().strip()
                       for key in ("title", "year", "season", "episode", "release")))

    def search(self):
        if self.busy:
            return
        ids = [key for key, var in self.enabled.items() if var.get()]
        if not ids:
            self.status.set("No subtitle sources configured." if not self.registry.providers else "No sources enabled.")
            return
        try:
            movie = self.current_movie()
        except ValueError as exc:
            self.notify(str(exc))
            return
        self.search_cancel = threading.Event()
        self.search_id += 1
        generation = self.search_id
        self.results.clear()
        self.table.delete(*self.table.get_children())
        self.busy = True
        self.search_button.configure(state="disabled")
        self.status.set("Searching subtitles…")
        self.search_errors = []
        self.query = Query(movie, tuple(self.languages()))
        emit = lambda kind, key, value: self.events.put(("search", generation, kind, key, value))
        threading.Thread(target=self.engine.run, args=(
            self.query, ids, self.search_cancel, emit), daemon=True).start()

    def languages(self):
        return [x.strip().lower() for x in self.language.get().split(",") if x.strip()] or ["vi", "en"]

    def cancel(self):
        self.search_cancel.set()
        self.download_cancel.set()
        self.status.set("Cancellation requested.")

    def result_selected(self, event=None):
        selected = self.table.selection()
        if selected:
            self.reason.set(self.results[selected[0]][1] + " • Synchronization is not guaranteed.")

    def download(self):
        selected = self.table.selection()
        if not selected or self.downloading:
            self.status.set("Choose a result to download." if not selected else "A download is already in progress.")
            return
        result = self.results[selected[0]][0]
        provider = self.registry.providers[result.provider]
        if not provider.capabilities.download:
            self.status.set("This provider does not support downloads.")
            return
        if not self.download_slots.acquire(blocking=False):
            self.status.set("Previous download is still running; wait for the provider.")
            return
        self.download_cancel = threading.Event()
        context = Context(self.download_cancel, time.monotonic() + provider.capabilities.timeout)
        self.download_deadline = context.deadline
        self.download_id += 1
        generation = self.download_id
        self.downloading = True
        self.status.set("Downloading subtitle…")

        def worker():
            try:
                name, data = self.engine.download(result, context)
                context.check()
                candidates = unpack_subtitles(name, data)
                self.events.put(("download", generation, candidates, None))
            except Exception as exc:
                self.events.put(("download", generation, None, error_text(exc)))
            finally:
                self.download_slots.release()
        threading.Thread(target=worker, daemon=True).start()

    def import_dialog(self):
        value = filedialog.askopenfilename(title="Import subtitle",
                                          filetypes=[("Subtitle / ZIP", "*.srt *.ass *.ssa *.vtt *.zip")])
        if value:
            self.import_file(value)
            self.show_tools(self.workflow)

    def import_file(self, value):
        try:
            path = Path(value)
            with path.open("rb") as stream:
                data = stream.read(MAX_ARCHIVE + 1)
            candidates = unpack_subtitles(path.name, data)
            self.download_cancel.set()
            self.download_id += 1
            self.downloading = False
            self.set_candidates(candidates)
        except Exception as exc:
            self.notify(str(exc))

    def set_candidates(self, candidates):
        self.candidates = candidates
        self.candidate.configure(values=[name for name, data in candidates])
        self.candidate.current(0)
        self.show_candidate()
        self.status.set(f"Imported {len(candidates)} subtitles. Choose a file and check its contents before saving.")

    def show_candidate(self, event=None):
        index = self.candidate.current()
        self.selected_data = None
        self.saved_path = ""
        self.saved_label.configure(text="No subtitle saved")
        if not 0 <= index < len(self.candidates):
            return
        name, data = self.candidates[index]
        try:
            text = decode_subtitle(data, self.encoding.get())
            self.selected_data = data
            self.selected_name = name
            preview = text[:60000]
            if len(text) > 60000:
                preview += "\n\n[… preview shortened; the full subtitle is preserved when saved …]"
        except Exception as exc:
            preview = str(exc)
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", preview)
        self.preview.configure(state="disabled")

    def save(self, on_saved=None):
        if self.selected_data is None:
            self.notify("Choose a valid subtitle and encoding before saving.")
            return None
        movie = Path(self.vars["movie"].get()) if self.vars["movie"].get() else None
        directory = self.output_dir.get() or str(self.home)
        if self.beside.get() and movie and movie.is_file():
            directory = str(movie.parent)
        name = Path(self.selected_name).name
        if movie and movie.is_file():
            # Do not infer a language from the user's preference.
            name = movie.stem + Path(name).suffix
        path = filedialog.asksaveasfilename(title="Save subtitle", initialdir=directory, initialfile=name,
                                          defaultextension=Path(name).suffix,
                                          filetypes=[("Subtitle", "*.srt *.ass *.ssa *.vtt")],
                                          confirmoverwrite=False)
        if not path:
            return None
        destination = Path(path)
        try:
            # A movie must never be overwritten, even if it has a strange extension.
            if movie and (destination.resolve() == movie.resolve()
                          or (destination.exists() and movie.exists() and destination.samefile(movie))):
                raise ValueError("Video files must never be overwritten.")
            def write(overwrite=False):
                try:
                    save_subtitle(destination, self.selected_data, overwrite=overwrite)
                    self.saved_path = str(destination)
                    self.saved_label.configure(text=f"Saved: {destination.name}")
                    self.status.set(f"Saved subtitle: {destination}")
                    if on_saved:
                        on_saved(str(destination))
                    return str(destination)
                except Exception as exc:
                    self.notify(str(exc))
            if destination.exists():
                # Capture bytes and paths now: an inline choice may be answered later.
                data = bytes(self.selected_data)
                def replace_existing():
                    try:
                        save_subtitle(destination, data, overwrite=True)
                        self.saved_path = str(destination)
                        self.saved_label.configure(text=f"Saved: {destination.name}")
                        self.notify(f"Saved subtitle: {destination}")
                        if on_saved:
                            on_saved(str(destination))
                    except Exception as exc:
                        self.notify(str(exc))
                self.confirm_inline(f"Replace existing subtitle {destination.name}?", replace_existing, "Replace subtitle")
                return None
            return write()
        except Exception as exc:
            self.notify(str(exc))
            return None

    def save_and_open(self):
        movie = self.vars["movie"].get()
        kind, executable = self.player_kind.get(), self.player_path.get()
        def open_saved(subtitle):
            try:
                launch(kind, executable, movie, subtitle)
                self.status.set("Opened the movie with subtitles in the configured player.")
            except Exception as exc:
                self.notify(str(exc))
        if self.saved_path:
            open_saved(self.saved_path)
        else:
            self.save(on_saved=open_saved)

    def filter_fonts(self, event=None):
        if event and event.keysym in ('Return','Escape','Up','Down','Left','Right'):
            return
        query = self.font_choice.get().casefold()
        self.font_picker.configure(values=[f for f in self.theme_manager.font_families if query in f.casefold()])

    def change_font(self, event=None):
        requested = self.font_choice.get().strip()
        if requested.casefold() not in {f.casefold() for f in self.theme_manager.font_families}:
            self.status.set('Choose an installed Windows font from the list.')
            return
        chosen = self.theme_manager.set_font(requested)
        self.font_choice.set(chosen)
        self.font_picker.configure(values=self.theme_manager.font_families)
        self.settings['font_family'] = chosen
        if self.settings_ok:
            try:
                write_json(self.data / 'settings.json', self.settings)
                self.status.set('Font saved: ' + chosen)
            except OSError:
                self.status.set('Font applied for this session; could not save the preference.')
        else:
            self.status.set('Font applied for this session; invalid settings file was preserved.')

    def update_glass_readout(self):
        strength = self.theme_manager.glass_strength
        self.glass_readout.set(f'{strength}% · opacity {round(100-strength*.35)}%')

    def change_glass(self, value):
        strength = self.theme_manager.set_glass(value)
        self.settings['glass_strength'] = strength
        self.update_glass_readout()
        if getattr(self, 'glass_save_timer', None):
            self.root.after_cancel(self.glass_save_timer)
        self.glass_save_timer = self.root.after(250, self.save_glass)

    def save_glass(self):
        self.glass_save_timer = None
        if self.settings_ok:
            try:
                write_json(self.data / 'settings.json', self.settings)
            except OSError:
                self.status.set('Glass effect applied; could not save the preference.')

    def change_theme(self, event=None):
        key = next((key for key, palette in THEMES.items() if palette[0] == self.theme_label.get()), 'blue')
        self.theme_key = self.theme_manager.apply(key)
        self.settings['theme'] = self.theme_key
        if not self.settings_ok:
            self.status.set('Theme applied for this session; invalid settings file was preserved.')
            return
        try:
            write_json(self.data / 'settings.json', self.settings)
            self.status.set('Theme saved: ' + THEMES[self.theme_key][0])
        except OSError:
            self.status.set('Theme applied for this session; could not save the preference.')

    def persist(self, notify=True):
        if not self.settings_ok:
            if notify:
                self.notify("settings.json is invalid and was not overwritten.")
            return
        self.settings.update(languages=",".join(self.languages()), player_kind=self.player_kind.get(),
                             player_path=self.player_path.get(), output_dir=self.output_dir.get(),
                             save_beside=self.beside.get(), geometry=self.root.geometry(),
                             disabled_sources=[k for k, v in self.enabled.items() if not v.get()])
        try:
            write_json(self.data / "settings.json", self.settings)
            if notify:
                self.status.set("Settings saved.")
        except OSError:
            if notify:
                self.notify("Could not write settings to the data folder.")

    def poll(self):
        if self.downloading and (self.download_cancel.is_set() or time.monotonic() > self.download_deadline):
            self.downloading = False
            self.download_cancel.set()
            self.download_id += 1
            self.status.set("Download cancelled or provider timed out.")
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if event[0] == "download":
                _, generation, candidates, error = event
                if generation == self.download_id:
                    self.downloading = False
                    if error:
                        self.status.set(f"Could not download subtitle ({error}).")
                    else:
                        self.set_candidates(candidates)
            else:
                _, generation, kind, key, value = event
                if generation != self.search_id:
                    continue
                if kind == "result":
                    score, reason = match_score(self.query.movie, value.release, value.title,
                                                value.language, list(self.query.languages))
                    item = self.table.insert("", "end", values=(
                        self.registry.providers[key].capabilities.name, value.language,
                        value.release or value.title, value.uploader or "—", value.quality or "—", score))
                    self.results[item] = (value, reason, score)
                elif kind == "error":
                    self.search_errors.append(f"{self.registry.providers[key].capabilities.name}: {value}")
                elif kind == "done":
                    self.busy = False
                    self.search_button.configure(state="normal")
                    for index, item in enumerate(sorted(self.results, key=lambda i: self.results[i][2], reverse=True)):
                        self.table.move(item, "", index)
                    self.status.set(("Search cancelled" if value == "cancelled" else "Search finished")
                                    + f" • {len(self.results)} results"
                                    + (" • " + "; ".join(self.search_errors) if self.search_errors else ""))
        inbox = self.data / "inbox"
        if inbox.exists():
            for path in sorted(inbox.glob("*.json"))[:10]:
                if len(self.browser_pending) >= 30:
                    break
                try:
                    if path.stat().st_size > 65536:
                        raise ValueError()
                    value = validate_message(json.loads(path.read_text("utf-8")))
                    self.browser_pending.append((path, value))
                    # Keep request on disk until the user applies it.
                    path.rename(path.with_suffix(".pending"))
                    self.browser_pending[-1] = (path.with_suffix(".pending"), value)
                    self.status.set("A browser request is available. Receive it to check the title.")
                except (OSError, ValueError):
                    self.status.set("Invalid browser request ignored.")
                    try:
                        path.rename(path.with_suffix(".invalid"))
                    except OSError:
                        pass
            if self.browser_pending:
                self.browser_note.set(f"There are {len(self.browser_pending)} browser requests. Receive one to check the title.")
                self.receive_button.configure(text=f"Receive from browser ({len(self.browser_pending)})")
        self.root.after(150, self.poll)

    def take_browser(self):
        if not self.browser_pending:
            self.status.set("No new browser requests.")
            return
        path, value = self.browser_pending.pop(0)
        # Clear the previous movie so a browser search cannot save beside an unrelated film.
        self.vars["movie"].set("")
        self.vars["url"].set(value["url"])
        self.apply_movie(parse_movie(value["selection"] or value["title"]))
        path.unlink(missing_ok=True)
        self.show_tools(self.workflow)
        self.status.set("Browser request received. Check the title, then search.")
        self.browser_note.set(f"Remaining: {len(self.browser_pending)} requests.")
        self.receive_button.configure(text=f"Receive from browser ({len(self.browser_pending)})")

    def run(self):
        # Recover unapplied messages from a previous launch.
        inbox = self.data / "inbox"
        if inbox.exists():
            for path in inbox.glob("*.pending"):
                path.rename(path.with_suffix(".json"))
        self.root.mainloop()

    def close(self):
        if hasattr(self, "library"):
            self.library.close()
            vocabulary = getattr(self.library, "vocabulary_window", None)
            if vocabulary:
                vocabulary.stop()
        self.search_cancel.set()
        self.download_cancel.set()
        self.persist(notify=False)
        for timer in self.root.tk.splitlist(self.root.tk.call("after", "info")):
            self.root.after_cancel(timer)
        self.root.destroy()
