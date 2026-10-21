"""Three simultaneous lists, backed by the shared folder/qBittorrent workflow."""
from dataclasses import replace, asdict
import hashlib
import json
from pathlib import Path
import threading
import tkinter as tk
from tkinter import ttk, filedialog

from .library_ui import LibraryUI, table
from .batch import Episode, scan_folder, rank, exact_filename
from .core import Movie, match_score, decode_subtitle, save_subtitle, MAX_SUBTITLE, SUB_EXTENSIONS
from .providers import Query, Result
from .storage import write_json
from .languages import LANGUAGES, LABEL_TO_CODE, CODE_TO_LABEL
from .library_folders import discover_library


class SimpleLibraryUI(LibraryUI):
    def __init__(self, app):
        self.pending_snapshot = None
        super().__init__(app)
        self.root.after(400, self.restore_pending)
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
        self.auto_pending = set()
        self.reported_saves = {}
        self.reported_prepared = set()
        self.recursive = tk.BooleanVar(value=True)
        self.title = tk.StringVar()
        self.season = tk.StringVar()
        self.language = self.app.language
        self.wait_download = tk.BooleanVar(value=True)
        icon = self.app.theme_manager.icon
        bar = ttk.Frame(self.btab)
        bar.pack(fill="x", pady=(0, 9))
        primary = ttk.Frame(bar)
        utility = ttk.Frame(bar)
        primary.grid(row=0, column=0, sticky='w')
        utility.grid(row=0, column=1, sticky='e')
        bar.columnconfigure(1, weight=1)
        def reflow(event):
            compact = event.width < primary.winfo_reqwidth() + utility.winfo_reqwidth() + 12
            utility.grid(row=1 if compact else 0, column=0 if compact else 1,
                         columnspan=2 if compact else 1, sticky='e', pady=(5,0) if compact else 0)
        bar.bind('<Configure>', reflow)
        ttk.Button(primary, text="Library folder…", style="Accent.TButton", command=self.scan).pack(side="left")
        ttk.Button(primary, text="Refresh", image=icon("refresh"), compound="left", command=self.refresh_library).pack(side="left", padx=(6,0))
        ttk.Button(primary, text="Find subtitles", image=icon("search"), compound="left", command=self.search_batch).pack(side="left", padx=8)
        ttk.Button(primary, text="Cancel", image=icon("close"), compound="left", command=self.cancel_batch_work).pack(side="left")
        ttk.Button(utility, text="Settings", image=icon("settings"), compound="left", command=lambda: self.app.show_tools(self.app.sources)).pack(side="right")
        ttk.Button(utility, text="Appearance", image=icon("appearance"), compound="left", command=self.app.show_appearance).pack(side="right", padx=5)
        ttk.Button(utility, text="Torrents", image=icon("torrent"), compound="left", command=self.app.show_torrents).pack(side="right")
        ttk.Button(utility, text="Preview", image=icon("play"), compound="left", command=lambda: self.app.show_tools(self.app.workflow)).pack(side="right", padx=5)
        ttk.Button(utility, text="Vocabulary…", command=self.show_vocabulary).pack(side="right", padx=5)
        info = ttk.Frame(self.btab)
        info.pack(fill="x", pady=(0, 9))
        self.language_label = tk.StringVar(value=CODE_TO_LABEL.get(self.language.get(), "Vietnamese"))
        language_box = ttk.Combobox(info, textvariable=self.language_label,
            values=tuple(label for label, _ in LANGUAGES), width=22, state="readonly")
        language_box.pack(side="right")
        language_box.bind("<<ComboboxSelected>>", lambda e: self.language.set(LABEL_TO_CODE[self.language_label.get()]))
        ttk.Label(info, text="Languages", style="Hint.TLabel").pack(side="right", padx=8)
        self.folder_label = tk.StringVar(value="Choose a folder, or import a torrent from Torrents.")
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
            ("progress", "Video", 50), ("sub", "Subtitle", 80), ("state", "Status", 120)], height=1)
        self.batch_table.configure(displaycolumns=("file", "state"))
        self.batch_table.column('state',width=110,minwidth=105,stretch=False)
        self.batch_table.column('file',width=150,minwidth=80)
        self.batch_table.bind("<<TreeviewSelect>>", lambda e: self.show_candidates())
        self.batch_table.bind("<Double-1>", lambda e: self.edit())
        actions = ttk.Frame(movie_pane)
        actions.pack(fill="x")
        ttk.Button(actions, text="Edit…", image=icon("edit"), compound="left", command=self.edit).pack(side="left")
        ttk.Button(actions, text="Open player", image=icon("play"), compound="left", command=self.open_episode).pack(side="left", padx=5)
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
        self.notice = tk.StringVar(value="Existing subtitles are skipped. Video files are never renamed.")
        ttk.Label(footer, textvariable=self.notice, style="Hint.TLabel", wraplength=1080).pack(anchor="w")

    def show_vocabulary(self):
        from .vocabulary_ui import VocabularyWindow
        current = getattr(self, 'vocabulary_window', None)
        if current and current.window.winfo_exists():
            current.window.deiconify()
            current.window.lift()
            return
        folder = self.library_folders.get(self.movie_choice.get(), getattr(self, 'current_folder', ''))
        self.vocabulary_window = VocabularyWindow(self.app, folder)

    def set_rows(self, rows):
        self.auto_pending.clear()
        self.automatic_rows.clear()
        self.reported_saves.clear()
        self.reported_prepared.clear()
        super().set_rows(rows)
        if rows:
            self.batch_table.selection_set("0")
            self.folder_label.set(f"{len(rows)} movie files · {rows[0].path.parent}")
        else:
            self.folder_label.set("No video files found.")

    def redraw(self):
        super().redraw()
        if not self.batch_table.selection() and self.rows:
            self.batch_table.selection_set("0")
        for index, row in enumerate(self.rows):
            if row.state != "Exact filename — auto-download":
                self.auto_pending.discard(index)
            if row.selected and exact_filename(row.path, row.selected) and row.state == "Exact filename — auto-download":
                self.auto_pending.add(index)
                self.automatic_rows.add(index)
            if row.saved and self.reported_saves.get(index) != row.saved:
                self.reported_saves[index] = row.saved
                prefix = "Auto-saved" if index in self.automatic_rows else "Saved"
                self.notice.set(f"{prefix} from {row.selected.provider}: {row.saved}")
            if row.selected and index in self.queued and index not in self.reported_prepared:
                self.reported_prepared.add(index)
                prefix = "Auto-downloaded" if index in self.automatic_rows else "Downloaded"
                self.notice.set(f"{prefix} from {row.selected.provider}; waiting for video: {row.path.name}")
        self.show_candidates()
        self.persist_pending()

    def persist_pending(self):
        records = []
        for index in sorted(self.queued):
            row = self.rows[index]
            if not row.selected:
                continue
            prepared = self.prepared.get((index, row.selected.provider, row.selected.id))
            if not prepared:
                continue
            name, data = prepared
            suffix = Path(name).suffix.lower()
            cache_file = self.app.data / "pending" / (hashlib.sha256(data).hexdigest() + suffix)
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            if not cache_file.exists():
                save_subtitle(cache_file, data)
            records.append({"path": str(row.path), "movie": asdict(row.movie), "selected": asdict(row.selected),
                "candidates": [asdict(r) for _, r in row.candidates[:100]],
                "torrent_hash": row.torrent_hash, "file_index": row.file_index, "progress": row.progress,
                "cached_subtitle": cache_file.name, "automatic": index in self.automatic_rows})
        snapshot = json.dumps(records, sort_keys=True)
        if snapshot != self.pending_snapshot:
            write_json(self.app.data / "pending-subtitles.json", records)
            self.pending_snapshot = snapshot

    def restore_pending(self):
        path = self.app.data / "pending-subtitles.json"
        if not path.exists() or self.rows or self.batch_busy:
            return
        try:
            records = json.loads(path.read_text("utf-8"))
            if not isinstance(records, list) or len(records) > 5000:
                raise ValueError("Invalid pending subtitle queue.")
            rows, prepared, automatic = [], {}, set()
            for record in records:
                cache_root = (self.app.data / "pending").resolve()
                cache_file = (cache_root / record["cached_subtitle"]).resolve()
                if cache_file.parent != cache_root or cache_file.suffix not in SUB_EXTENSIONS:
                    raise ValueError("Invalid cached subtitle path.")
                if cache_file.stat().st_size > MAX_SUBTITLE:
                    raise ValueError("Cached subtitle too large.")
                data = cache_file.read_bytes()
                decode_subtitle(data)
                result = Result(**record["selected"])
                index = len(rows)
                row = Episode(Path(record["path"]), Movie(**record["movie"]), selected=result,
                    candidates=[(100, Result(**r)) for r in record.get("candidates", [record["selected"]])],
                    state="Subtitle downloaded; waiting for video",
                    torrent_hash=record["torrent_hash"], file_index=record["file_index"], progress=record["progress"])
                rows.append(row)
                prepared[(index, result.provider, result.id)] = (cache_file.name, data)
                if record.get("automatic"):
                    automatic.add(index)
            self.set_rows(rows)
            self.prepared.update(prepared)
            self.automatic_rows.update(automatic)
            self.queued.update(range(len(rows)))
            self.redraw()
            if rows:
                self.bstatus.set(f"Restored {len(rows)} downloaded subtitles. Waiting for their videos to finish.")
        except Exception:
            self.bstatus.set("Could not restore the pending subtitle queue; its files were preserved.")

    def show_candidates(self):
        index = self.selected_row()
        row = self.rows[index] if index is not None and index < len(self.rows) else None
        for provider, view in self.source_views.items():
            selected = view.selection()
            view.delete(*view.get_children())
            count = 0
            if row:
                for candidate_index, (score, result) in enumerate(row.candidates):
                    if result.provider != provider:
                        continue
                    is_exact = exact_filename(row.path, result)
                    is_saved = bool(row.saved and row.selected == result)
                    view.insert("", "end", iid=str(candidate_index), values=(result.filename or result.release,
                        result.language, "Saved" if is_saved else "Exact filename" if is_exact else "Choose"),
                        tags=("saved" if is_saved else "exact" if is_exact else "",))
                    count += 1
            if selected and view.exists(selected[0]):
                view.selection_set(selected[0])
            elif count:
                view.selection_set(view.get_children()[0])
            self.source_summaries[provider].set(f"{count} results · {row.movie.title} · S{row.movie.season} E{row.movie.episode}" if row else "Select a movie file.")

    def scan(self):
        if self.batch_busy or self.queued:
            self.bstatus.set('Finish or cancel the current subtitle queue before changing the library.')
            return
        folder = filedialog.askdirectory(title="Set library and qBittorrent download folder",
                                        initialdir=self.app.settings.get('library_root') or None)
        if folder:
            self.app.settings['library_root'] = folder
            self.app.settings['library_selection'] = ''
            self.movie_choice.set('')
            self.app.persist(False)
            self.refresh_library()
            self.connect()

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
            if found is None:
                self.bstatus.set('Could not scan the library. Check the folder and try Refresh library.')
                return
            self.library_folders = found
            self.movie_picker.configure(values=list(found))
            if not found:
                self.movie_choice.set('')
                self.bstatus.set('No movie folders found in the library.')
                return
            if self.movie_choice.get() not in found:
                self.movie_choice.set(next(iter(found)))
            if not self.rows and not self.batch_busy and not self.queued:
                self.select_library_movie()
        self.run(lambda: discover_library(folder, excluded), done)

    def select_library_movie(self, event=None):
        if self.batch_busy or self.queued:
            self.movie_choice.set(self.app.settings.get('library_selection', ''))
            self.bstatus.set('Finish or cancel the current subtitle queue before switching movies.')
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
        self.run(lambda: scan_folder(folder, recursive, title, season), done)

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
        self.queued.clear()
        self.auto_pending.clear()
        self.batch_busy = True
        encoding = self.app.encoding.get()
        def job():
            for index, original in enumerate(self.rows):
                if self.cancel_batch.is_set():
                    break
                if not original.enabled:
                    continue
                row = replace(original, candidates=[], selected=None, state="Searching…")
                self.events.put(("row", index, replace(row)))
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
                self.app.engine.run(Query(row.movie, languages), ids, self.cancel_batch, emit)
                found.sort(key=lambda v: (not exact_filename(row.path, v[1]), languages.index(v[1].language), -v[0]))
                row.candidates = found
                exact = [r for _, r in found if exact_filename(row.path, r)]
                if self.cancel_batch.is_set():
                    row.state = "Cancelled"
                elif exact:
                    row.selected = exact[0]
                    row.state = "Exact filename — auto-download"
                elif found:
                    row.state = "Choose a subtitle"
                else:
                    row.state = "; ".join(errors) or "No matching results"
                self.events.put(("row", index, row))
                if exact and not self.cancel_batch.is_set():
                    try:
                        prepared_row, waiting = self.process_subtitle(replace(row), index, encoding)
                        self.events.put(("saved", index, prepared_row, waiting))
                    except Exception as exc:
                        from .sources import error_text
                        from .qbittorrent import QbitError
                        row.state = str(exc) if isinstance(exc, (ValueError, QbitError)) else error_text(exc)
                        self.events.put(("row", index, row))
            return True
        def done(_):
            self.batch_busy = False
            self.bstatus.set("Search finished. Exact filenames download automatically; choose other versions in either source list.")
            self.auto_pending.clear()
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
        self.queued.discard(index)
        self.redraw()
        self.download_batch(indices=[index])

    def cancel_batch_work(self):
        self.auto_pending.clear()
        super().cancel_batch_work()
        self.persist_pending()
