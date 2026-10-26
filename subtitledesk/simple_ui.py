"""Browse local movie folders and compare two subtitle sources side by side."""
from dataclasses import replace
from pathlib import Path
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .library_ui import LibraryUI, table
from .batch import scan_folder, rank, exact_filename, existing_subtitle
from .core import match_score
from .providers import Query
from .storage import dialog_directory
from .languages import LANGUAGES, LABEL_TO_CODE, CODE_TO_LABEL
from .library_folders import discover_library
from .recycle import recycle_video, validate_video
from .row_actions import MovieRowActions


class SimpleLibraryUI(LibraryUI):
    def __init__(self, app):
        super().__init__(app)
        self.library_folders = {}
        self.library_refreshing = False
        self.root.after(850, self.refresh_library)
        self.root.after_idle(self.balance_panes)

    def balance_panes(self):
        self.root.update_idletasks()
        width = self.panes.winfo_width()
        if width > 30:
            self.panes.sashpos(0, width // 3)
            self.panes.sashpos(1, width * 2 // 3)

    def build_batch(self):
        self.automatic_rows = set()
        self.reported_saves = {}
        self.recursive = tk.BooleanVar(value=True)
        self.title = tk.StringVar()
        self.season = tk.StringVar()
        self.language = self.app.language
        icon = self.app.theme_manager.icon
        bar = ttk.Frame(self.btab)
        bar.pack(fill="x", pady=(0, 9))
        primary = ttk.Frame(bar)
        primary.pack(side="left")
        ttk.Button(primary, text="Library folder…", style="Accent.TButton", command=self.scan).pack(side="left")
        ttk.Button(primary, text="Refresh", image=icon("refresh"), compound="left", command=self.refresh_library).pack(side="left", padx=(6,0))
        ttk.Button(primary, text="Find subtitles", image=icon("search"), compound="left", command=self.search_batch).pack(side="left", padx=8)
        ttk.Button(primary, text="Cancel", image=icon("close"), compound="left", command=self.cancel_batch_work).pack(side="left")
        info = ttk.Frame(self.btab)
        info.pack(fill="x", pady=(0, 9))
        self.language_label = tk.StringVar(value=CODE_TO_LABEL.get(self.language.get(), "Vietnamese"))
        language_box = ttk.Combobox(info, textvariable=self.language_label,
            values=tuple(label for label, _ in LANGUAGES), width=22, state="readonly")
        language_box.pack(side="right")
        language_box.bind("<<ComboboxSelected>>", lambda e: self.language.set(LABEL_TO_CODE[self.language_label.get()]))
        ttk.Label(info, text="Languages", style="Hint.TLabel").pack(side="right", padx=8)
        self.folder_label = tk.StringVar(value="Choose a movie library folder to browse your videos.")
        ttk.Label(info, textvariable=self.folder_label, style="Hint.TLabel").pack(side="left", fill="x", expand=True)
        self.panes = ttk.Panedwindow(self.btab, orient="horizontal")
        self.panes.pack(fill="both", expand=True)
        movie_pane = ttk.Frame(self.panes, padding=10, style='Card.TFrame')
        self.panes.add(movie_pane, weight=1)
        movie_heading = ttk.Frame(movie_pane)
        movie_heading.pack(fill='x', pady=(0,6))
        ttk.Label(movie_heading, text="Movie files", image=icon("film"), compound="left", style="CardTitle.TLabel").pack(side='left')
        self.movie_choice = tk.StringVar(value=self.app.settings.get('library_selection', ''))
        self.movie_picker = ttk.Combobox(movie_heading, textvariable=self.movie_choice,
                                        state='readonly', width=16)
        self.movie_picker.pack(side='left', fill='x', expand=True, padx=(10,0))
        self.movie_picker.bind('<<ComboboxSelected>>', self.select_library_movie)
        self.batch_table = table(movie_pane, [("use", "Use", 35), ("file", "Video", 240),
            ("title", "Title", 80), ("season", "Season", 40), ("episode", "Episode", 40),
            ("sub", "Subtitle", 80), ("state", "Status", 120),
            ("play", "Play", 56), ("delete", "Delete", 64)], height=1,
            selectmode="extended")
        self.batch_table.configure(displaycolumns=("file", "state", "play", "delete"))
        self.batch_table.column('state',width=80,minwidth=65,stretch=False)
        self.batch_table.column('file',width=150,minwidth=80)
        self.movie_actions = MovieRowActions(self.batch_table, self.movie_row_action)
        self.batch_table.bind("<<TreeviewSelect>>", lambda e: self.show_candidates())
        self.batch_table.bind("<Double-1>", self.open_movie)
        self.batch_table.bind("<Return>", self.open_movie)
        self.batch_table.bind("<Delete>", lambda e: (self.recycle_selected_movies(), "break")[1])
        self.batch_table.bind("<Control-a>", self.select_all_movies)
        self.batch_table.bind("<Control-A>", self.select_all_movies)
        self.batch_table.bind("<Button-3>", self.show_movie_menu)
        self.batch_table.bind("<Shift-F10>", lambda e: self.show_movie_menu(e, keyboard=True))
        self.batch_table.bind("<KeyPress-Menu>", lambda e: self.show_movie_menu(e, keyboard=True))
        self.movie_menu = tk.Menu(self.batch_table, tearoff=False)
        self.movie_menu.add_command(label="Open", accelerator="Enter", command=self.open_episode)
        self.movie_menu.add_command(label="Edit episode details…", command=self.edit)
        self.movie_menu.add_separator()
        self.movie_menu.add_command(label="Delete", accelerator="Del", command=self.recycle_selected_movies)
        ttk.Label(movie_pane, text="Play opens this episode. Delete moves its video to the Recycle Bin immediately.",
                  style="Hint.TLabel", wraplength=280).pack(anchor="w", pady=(7, 0))
        self.source_views = {}
        self.source_summaries = {}
        for provider, heading in (("subdl", "SubDL"), ("opensubtitles", "OpenSubtitles")):
            pane = ttk.Frame(self.panes, padding=10, style='Card.TFrame')
            self.panes.add(pane, weight=1)
            source_heading = ttk.Frame(pane, height=self.movie_picker.winfo_reqheight())
            source_heading.pack(fill='x', pady=(0,6))
            source_heading.pack_propagate(False)
            ttk.Label(source_heading, text=heading, image=icon('cloud' if provider=='subdl' else 'search'),
                      compound='left', style='CardTitle.TLabel').pack(side='left')
            view = table(pane, [("release", "Subtitle filename / release", 220),
                                ("lang", "Lang", 40), ("match", "Match", 95)], height=1)
            view.column('lang',width=42,minwidth=42,stretch=False)
            view.column('match',width=100,minwidth=95,stretch=False)
            view.column('release',width=150,minwidth=80)
            view.tag_configure("exact", background="#dceaff", foreground="#173c72")
            view.tag_configure("saved", background="#e5f3e9", foreground="#204c2d")
            view.bind("<Double-1>", lambda e, p=provider: self.download_choice(p))
            self.source_views[provider] = view
            summary = tk.StringVar(value="Select a movie file.")
            self.source_summaries[provider] = summary
            ttk.Label(pane, textvariable=summary, style="Hint.TLabel", wraplength=280).pack(anchor="w")
            ttk.Button(pane, text="Download & apply", image=icon("download"), compound="left", command=lambda p=provider:
                       self.download_choice(p)).pack(anchor="e", pady=(7, 0))
        footer = ttk.Frame(self.btab)
        footer.pack(side='bottom', fill='x', before=self.panes, pady=(10,0))
        self.bstatus = tk.StringVar(value="Exact filename matches are highlighted and downloaded automatically.")
        ttk.Label(footer, textvariable=self.bstatus, wraplength=1080).pack(anchor="w", pady=(0,3))
        self.notice = tk.StringVar(value="Language tracks are saved beside each video; existing files are protected.")
        ttk.Label(footer, textvariable=self.notice, style="Hint.TLabel", wraplength=1080).pack(anchor="w")

    def show_vocabulary(self):
        from .vocabulary_ui import VocabularyWindow
        current = getattr(self, 'vocabulary_window', None)
        if not current or current.closed:
            folder = self.library_folders.get(self.movie_choice.get(), getattr(self, 'current_folder', ''))
            self.vocabulary_window = VocabularyWindow(self.app, folder)
        self.app.pages.select(self.app.vocabulary_page)

    def set_rows(self, rows):
        self.automatic_rows.clear()
        self.reported_saves.clear()
        super().set_rows(rows)
        if rows:
            self.batch_table.selection_set("0")
            self.batch_table.focus("0")
            self.folder_label.set(f"{len(rows)} movie files · {rows[0].path.parent}")
        else:
            self.folder_label.set("No video files found.")

    def redraw(self):
        super().redraw()
        if not self.batch_table.selection() and self.rows:
            self.batch_table.selection_set("0")
        for index, row in enumerate(self.rows):
            if row.selected and exact_filename(row.path, row.selected) and row.state == "Exact filename — auto-download":
                self.automatic_rows.add(index)
            if row.saved and self.reported_saves.get(index) != row.saved:
                self.reported_saves[index] = row.saved
                prefix = "Auto-saved" if index in self.automatic_rows or row.state.startswith("Auto-saved") else "Saved"
                self.notice.set(f"{prefix} from {row.selected.provider}: {row.saved}"
                                if row.selected else f"{prefix} subtitle: {row.saved}")
        self.show_candidates()
        self.movie_actions.schedule()

    def show_candidates(self):
        index = self.selected_row()
        row = self.rows[index] if index is not None and index < len(self.rows) else None
        signature = (index, row.path if row else None,
                     tuple((score, result, row.saved_result_ids.get(result.language)) for score, result in row.candidates) if row else (),
                     row.saved if row else "")
        if getattr(self, '_candidate_signature', None) == signature:
            return
        self._candidate_signature = signature
        for provider, view in self.source_views.items():
            selected = view.selection()
            view.delete(*view.get_children())
            count = 0
            if row:
                for candidate_index, (score, result) in enumerate(row.candidates):
                    if result.provider != provider:
                        continue
                    is_exact = exact_filename(row.path, result)
                    is_saved = row.saved_result_ids.get(result.language) == (result.provider, result.id)
                    view.insert("", "end", iid=str(candidate_index), values=(result.filename or result.release,
                        result.language, "Saved" if is_saved else "Exact filename" if is_exact else "Choose"),
                        tags=("saved" if is_saved else "exact" if is_exact else "",))
                    count += 1
            if selected and view.exists(selected[0]):
                view.selection_set(selected[0])
            elif count:
                view.selection_set(view.get_children()[0])
            self.source_summaries[provider].set(f"{count} results · {row.movie.title} · S{row.movie.season} E{row.movie.episode}" if row else "Select a movie file.")

    def movie_row_action(self, item, action):
        # A row button always targets its own episode, even with a multi-selection.
        if not self.batch_table.exists(item) or int(item) >= len(self.rows):
            return
        self.batch_table.selection_set(item)
        self.batch_table.focus(item)
        if action == "play":
            self.open_episode()
        elif action == "delete":
            self.recycle_selected_movies()

    def open_movie(self, event=None):
        # Only a double-click on a real row opens a movie, never the header/empty space.
        if event is not None and event.type == tk.EventType.ButtonPress:
            item = self.batch_table.identify_row(event.y)
            if not item or self.batch_table.identify_region(event.x, event.y) not in ("cell", "tree"):
                return
            self.batch_table.selection_set(item)
            self.batch_table.focus(item)
        self.open_episode()
        return "break"

    def select_all_movies(self, event=None):
        items = self.batch_table.get_children()
        self.batch_table.selection_set(items)
        if items and not self.batch_table.focus():
            self.batch_table.focus(items[0])
        return "break"

    def show_movie_menu(self, event, keyboard=False):
        if keyboard:
            index = self.selected_row()
            if index is None:
                return "break"
            item = str(index)
            self.batch_table.see(item)
            x, y, width, height = self.batch_table.bbox(item)
            screen_x = self.batch_table.winfo_rootx() + x + min(width, 30)
            screen_y = self.batch_table.winfo_rooty() + y + height
        else:
            item = self.batch_table.identify_row(event.y)
            if not item:
                return "break"
            screen_x, screen_y = event.x_root, event.y_root
        if item not in self.batch_table.selection():
            self.batch_table.selection_set(item)
        self.batch_table.focus(item)
        self.batch_table.focus_set()
        state = "disabled" if self.batch_busy else "normal"
        self.movie_menu.entryconfigure("Open", state=state)
        self.movie_menu.entryconfigure("Edit episode details…", state=state)
        deleting = self.batch_busy or self.library_refreshing
        self.movie_menu.entryconfigure("Delete", state="disabled" if deleting else "normal")
        try:
            self.movie_menu.tk_popup(screen_x, screen_y)
        finally:
            self.movie_menu.grab_release()
        return "break"

    def recycle_selected_movies(self):
        selected = sorted({int(item) for item in self.batch_table.selection()})
        if not selected:
            self.bstatus.set("Select one or more movie files first. Use Ctrl+click for multiple files.")
            return
        if self.batch_busy or self.library_refreshing:
            self.bstatus.set("Finish the current subtitle work before moving videos to the Recycle Bin.")
            return
        rows = [self.rows[index] for index in selected]
        library_root = self.app.settings.get("library_root", "")
        try:
            for row in rows:
                validate_video(row.path, Path(library_root))
        except (OSError, ValueError) as exc:
            self.bstatus.set(str(exc))
            return
        moved, failures = [], []
        for index, row in zip(selected, rows):
            try:
                recycle_video(row.path, Path(library_root))
                moved.append(index)
            except (OSError, ValueError) as exc:
                failures.append(f"{row.path.name}: {exc}")
        if moved:
            removed = set(moved)
            self.batch_table.selection_remove(self.batch_table.selection())
            self.set_rows([row for index, row in enumerate(self.rows) if index not in removed])
            if self.rows:
                survivor = str(min(selected[0], len(self.rows) - 1))
                self.batch_table.selection_set(survivor)
                self.batch_table.focus(survivor)
            self.bstatus.set(f"Moved {len(moved)} video(s) to the Recycle Bin.")
            self.notice.set("Video files moved to the Recycle Bin. Subtitle files were left in place.")
        if failures:
            self.notice.set("; ".join(failures[:8]))
            self.bstatus.set(f"Moved {len(moved)} video(s); {len(failures)} could not be moved.")

    def scan(self):
        if self.batch_busy:
            self.bstatus.set('Finish or cancel the current subtitle work before changing the library.')
            return
        folder = filedialog.askdirectory(title="Choose movie library folder",
                                        initialdir=dialog_directory(self.app.settings.get('library_root')))
        if folder:
            self.app.settings['library_root'] = folder
            self.app.settings['library_selection'] = ''
            self.movie_choice.set('')
            self.app.persist(False)
            self.refresh_library()

    def refresh_library(self):
        folder = self.app.settings.get('library_root', '')
        if not folder or self.library_refreshing:
            return
        self.library_refreshing = True
        self.folder_label.set('Library: ' + folder)
        app_home = Path(__file__).resolve().parents[1]
        root = Path(folder).resolve()
        excluded = []
        if app_home.is_relative_to(root) and app_home != root:
            excluded.append(root / app_home.relative_to(root).parts[0])
        def done(found):
            self.library_refreshing = False
            if folder != self.app.settings.get("library_root", ""):
                return
            if found is None:
                self.bstatus.set('Could not scan the library. Check the folder and try Refresh library.')
                return
            self.library_folders = found
            self.movie_picker.configure(values=list(found))
            if not found:
                self.movie_choice.set('')
                if not self.batch_busy:
                    self.set_rows([])
                self.bstatus.set('No movie folders found in the library.')
                return
            if self.movie_choice.get() not in found:
                self.movie_choice.set(next(iter(found)))
            if not self.batch_busy:
                self.select_library_movie()
        self.run(lambda: discover_library(folder, excluded), done, scoped=False)

    def select_library_movie(self, event=None):
        if self.batch_busy:
            self.movie_choice.set(self.app.settings.get('library_selection', ''))
            self.bstatus.set('Finish or cancel the current subtitle work before switching movies.')
            return
        selected = self.movie_choice.get()
        folder = self.library_folders.get(selected)
        if folder:
            self.app.settings['library_selection'] = selected
            self.app.persist(False)
            self.load_folder(folder, recursive=Path(folder).resolve() != Path(self.app.settings['library_root']).resolve())

    def load_folder(self, folder, recursive=True):
        if self.batch_busy:
            return
        self.batch_busy = True
        title, season = self.title.get(), self.season.get()
        def done(rows):
            self.batch_busy = False
            if rows is not None:
                self.current_folder = str(folder)
                self.set_rows(rows)
                self.bstatus.set("Select a movie to compare both sources. Click Find subtitles to search the folder.")
        languages = tuple(self.app.languages())
        self.run(lambda: scan_folder(folder, recursive, title, season, languages), done)

    def search_batch(self):
        if self.batch_busy or not self.rows:
            return
        ids = [key for key, value in self.app.enabled.items() if value.get()]
        if not ids:
            self.bstatus.set("Enable a source and enter its API key in Settings.")
            return
        languages = tuple(v.strip().lower() for v in self.language.get().split(",") if v.strip())
        if not languages:
            return
        self.cancel_batch = threading.Event()
        self.batch_busy = True
        encoding = self.app.encoding.get()
        generation = self.generation
        cancel = self.cancel_batch
        snapshot = [replace(row, saved_languages=dict(row.saved_languages)) for row in self.rows]
        def post(kind, index, row):
            self.events.put((kind, generation, index, row.path, replace(row, saved_languages=dict(row.saved_languages))))
        def job():
            for index, original in enumerate(snapshot):
                if cancel.is_set():
                    break
                if original.ambiguous:
                    continue
                if all(existing_subtitle(original.path, lang) for lang in languages):
                    continue
                row = replace(original, candidates=[], selected=None, state="Searching…")
                post("row", index, row)
                found, errors = [], []
                def emit(kind, key, value):
                    if kind == "result":
                        if value.language not in languages:
                            return
                        if row.movie.season.isdecimal() and row.movie.episode.isdecimal():
                            score = rank(row.movie, value, value.language)
                        elif row.movie.season or row.movie.episode:
                            score = None
                        else:
                            score = match_score(row.movie, value.release, value.title, value.language, list(languages))[0]
                        if score is not None:
                            found.append((score, value))
                    elif kind == "error":
                        errors.append(f"{key}: {value}")
                self.app.engine.run(Query(row.movie, languages), ids, cancel, emit)
                found.sort(key=lambda v: (not exact_filename(row.path, v[1]), languages.index(v[1].language), -v[0]))
                row.candidates = found
                exact = []
                exact_languages = set()
                for _, result in found:
                    if exact_filename(row.path, result) and result.language not in exact_languages:
                        exact.append(result)
                        exact_languages.add(result.language)
                if cancel.is_set():
                    row.state = "Cancelled"
                elif exact:
                    row.selected = exact[0]
                    row.state = "Exact filename — auto-download"
                elif found:
                    row.state = "Choose a subtitle"
                else:
                    row.state = "; ".join(errors) or "No matching results"
                post("row", index, row)
                if exact and not cancel.is_set():
                    for result in exact:
                        if cancel.is_set():
                            break
                        try:
                            row = self.process_subtitle(replace(row, selected=result), index, encoding, cancel)
                            row.state = "Auto-saved: " + ", ".join(row.saved_languages)
                            post("saved", index, row)
                        except Exception as exc:
                            from .sources import error_text
                            row.state = str(exc) if isinstance(exc, ValueError) else error_text(exc)
                            post("row", index, row)
            return True
        def done(_):
            self.batch_busy = False
            self.bstatus.set("Search cancelled. Saved subtitles were retained." if cancel.is_set() else
                             "Search finished. Exact filenames download automatically; choose other versions in either source list.")
        self.run(job, done)

    def download_choice(self, provider):
        index = self.selected_row()
        selected = self.source_views[provider].selection()
        if index is None or not selected:
            return
        if self.batch_busy:
            self.bstatus.set("Please wait for the current search/download, or cancel it first.")
            return
        row = self.rows[index]
        row.selected = row.candidates[int(selected[0])][1]
        row.enabled = True
        self.automatic_rows.discard(index)
        self.redraw()
        self.download_batch(indices=[index])
