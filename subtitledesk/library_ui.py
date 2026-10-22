from dataclasses import replace
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .batch import Episode, identify, scan_folder, rank, select_file, save_episode, existing_subtitle
from .core import Movie, VIDEO_EXTENSIONS, unpack_subtitles, decode_subtitle
from .providers import Query, Context
from .qbittorrent import QbitClient, QbitError, DownloadShutdown, content_file
from .sources import error_text


def size(value):
    if value is None or value < 0:
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


def count(value):
    return "?" if value is None or value < 0 else str(value)


def table(frame, columns, height=8, selectmode="browse"):
    container = ttk.Frame(frame)
    container.pack(fill="both", expand=True, pady=6)
    view = ttk.Treeview(container, columns=[c[0] for c in columns], show="headings",
                        selectmode=selectmode, height=height)
    for key, label, width in columns:
        view.heading(key, text=label, anchor="w", command=lambda k=key: sort_table(view, k))
        view.column(key, width=width, minwidth=40)
    sy = ttk.Scrollbar(container, orient="vertical", command=view.yview)
    sx = ttk.Scrollbar(container, orient="horizontal", command=view.xview)
    def scroll_x(first, last):
        sx.set(first, last)
        if float(first) <= 0 and float(last) >= 1:
            sx.grid_remove()
        else:
            sx.grid(row=1, column=0, sticky="ew")
    view.configure(yscrollcommand=sy.set, xscrollcommand=scroll_x)
    view.grid(row=0, column=0, sticky="nsew")
    sy.grid(row=0, column=1, sticky="ns")
    sx.grid(row=1, column=0, sticky="ew")
    container.columnconfigure(0, weight=1)
    container.rowconfigure(0, weight=1)
    return view


def sort_table(view, column):
    def key(item):
        text = view.set(item, column)
        try:
            return (0, float(text.replace("%", "").split(" / ")[0]))
        except ValueError:
            return (1, text.casefold())
    reverse = getattr(view, "_sort", None) != (column, True)
    for index, item in enumerate(sorted(view.get_children(), key=key, reverse=reverse)):
        view.move(item, "", index)
    view._sort = (column, reverse)


class LibraryUI:
    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.events = queue.Queue()
        self.client = None
        self.connected = False
        self.connecting = False
        self.refreshing = False
        self.searching = False
        self.cancel_search = threading.Event()
        self.cancel_batch = threading.Event()
        self.batch_busy = False
        self.rows = []
        self.torrents = {}
        self.hits = {}
        self.last_refresh = 0
        self.last_batch = 0
        self.queued = set()
        self.cache = None
        self.prepared = {}
        self.stopped = False
        self.download_shutdown = DownloadShutdown()
        self.shutting_down_qbit = False
        self.qtab = ttk.Frame(app.torrent_window, padding=10)
        self.qtab.pack(fill="both", expand=True)
        self.btab = ttk.Frame(app.main_content)
        self.btab.pack(fill="both", expand=True)
        self.build_qbit()
        self.build_batch()
        self.root.after(250, self.poll)

    def run(self, function, callback=None):
        def worker():
            try:
                value = function()
                self.events.put(("callback", callback, value))
            except Exception as exc:
                text = str(exc) if isinstance(exc, (QbitError, ValueError)) else error_text(exc)
                self.events.put(("error", text))
                self.events.put(("callback", callback, None))
        threading.Thread(target=worker, daemon=True).start()

    def build_qbit(self):
        s = self.app.settings
        self.qurl = tk.StringVar(value=s.get("qbit_url", "http://127.0.0.1:18080"))
        self.quser = tk.StringVar(value=s.get("qbit_username", "subtitledesk"))
        self.qpassword = tk.StringVar()
        self.qexe = tk.StringVar(value=s.get("qbit_exe", r"D:\Program\qBittorrent\qbittorrent.exe"))
        setup = ttk.LabelFrame(self.qtab, text="Local connection", padding=6)
        setup.pack(fill="x")
        for col, (label, var, width) in enumerate((
            ("WebUI URL", self.qurl, 28), ("Username", self.quser, 17), ("New password (if changed)", self.qpassword, 24))):
            ttk.Label(setup, text=label).grid(row=0, column=col, sticky="w")
            ttk.Entry(setup, textvariable=var, width=width, show="•" if col == 2 else "").grid(row=1, column=col, sticky="ew", padx=(0, 6))
            setup.columnconfigure(col, weight=1)
        ttk.Button(setup, text="Connect / open qBittorrent", command=self.connect).grid(row=1, column=3)
        ttk.Label(setup, text="qBittorrent opens when you enter Torrents and exits after observed downloads finish.",
                  style="Hint.TLabel").grid(row=2, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Button(setup, text="Choose qbittorrent.exe…", command=self.pick_qexe).grid(row=2, column=2, sticky="w")
        self.qstatus = tk.StringVar(value="Not connected. Enable WebUI or use the existing connection settings.")
        ttk.Label(self.qtab, textvariable=self.qstatus, wraplength=1000).pack(anchor="w", pady=4)
        tabs = ttk.Notebook(self.qtab)
        tabs.pack(fill="both", expand=True)
        current = ttk.Frame(tabs, padding=6)
        search = ttk.Frame(tabs, padding=6)
        tabs.add(current, text="Downloads")
        tabs.add(search, text="Torrent search")
        row = ttk.Frame(current)
        row.pack(fill="x")
        ttk.Button(row, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Button(row, text="Import selected movie files", command=self.import_torrent).pack(side="left", padx=6)
        ttk.Button(row, text="Peer details", command=self.show_peers).pack(side="left")
        self.downloads = table(current, [("name", "Torrent name", 290), ("progress", "%", 60),
            ("seeds", "Seeds connected / total", 135), ("peers", "Peers connected / total", 135),
            ("down", "Download", 95), ("up", "Upload", 85), ("size", "Size", 100),
            ("eta", "Remaining", 80), ("state", "Status", 110)])
        self.downloads.bind("<Double-1>", lambda e: self.import_torrent())
        row = ttk.Frame(search)
        row.pack(fill="x")
        self.pattern = tk.StringVar()
        self.plugin = tk.StringVar(value="enabled")
        ttk.Entry(row, textvariable=self.pattern).pack(side="left", fill="x", expand=True)
        self.plugin_box = ttk.Combobox(row, textvariable=self.plugin, values=("enabled",), width=20, state="readonly")
        self.plugin_box.pack(side="left", padx=4)
        ttk.Button(row, text="Search", command=self.search).pack(side="left")
        ttk.Button(row, text="Cancel", command=lambda: self.cancel_search.set()).pack(side="left", padx=4)
        self.search_results = table(search, [("name", "Torrent name", 400), ("size", "Size", 100),
            ("seeds", "Seeds", 70), ("peers", "Leechers", 70), ("site", "Source", 170)])
        row = ttk.Frame(search)
        row.pack(fill="x")
        ttk.Button(row, text="Download selected torrent…", command=self.add_selected).pack(side="left")
        ttk.Button(row, text="Search subtitles by title", command=self.subtitle_from_hit).pack(side="left", padx=6)
        row = ttk.LabelFrame(self.qtab, text="Add torrent", padding=5)
        row.pack(fill="x", pady=(6, 0))
        self.magnet = tk.StringVar()
        ttk.Entry(row, textvariable=self.magnet).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Add magnet / URL…", command=self.add_magnet).pack(side="left", padx=4)
        ttk.Button(row, text="File .torrent…", command=self.add_torrent_file).pack(side="left")

    def persist(self):
        self.app.settings.update(qbit_url=self.qurl.get().strip(), qbit_username=self.quser.get().strip(),
                                 qbit_exe=self.qexe.get())
        self.app.persist(False)

    def pick_qexe(self):
        path = filedialog.askopenfilename(filetypes=[("qBittorrent", "qbittorrent.exe")])
        if path:
            self.qexe.set(path)
            self.persist()

    def connect(self):
        if self.connected or self.connecting or self.shutting_down_qbit or self.searching or self.batch_busy:
            return
        if self.qpassword.get():
            self.app.secrets.set("qbittorrent", "password", self.qpassword.get())
            self.qpassword.set("")
        self.persist()
        try:
            client = QbitClient(self.qurl.get().strip(), self.quser.get().strip(),
                               self.app.secrets.get("qbittorrent", "password"), self.qexe.get())
        except Exception as exc:
            self.qstatus.set(str(exc))
            return
        self.connecting = True
        self.connected = False
        self.qstatus.set("Connecting / starting qBittorrent…")
        library_root = self.app.settings.get('library_root', '')
        def job():
            version = client.connect(launch=True)
            if library_root:
                client.set_default_save_path(library_root)
            return client, version, client.plugins()
        def done(value):
            self.connecting = False
            if value:
                self.client, version, plugins = value
                self.connected = True
                self.qstatus.set(f"Connected to qBittorrent {version} • updates every 5 seconds")
                self.plugin_box.configure(values=["enabled"] + [p["name"] for p in plugins if p.get("enabled")])
                self.refresh()
        self.run(job, done)

    def require_client(self):
        if not self.connected:
            self.qstatus.set("Connect to qBittorrent first.")
            return False
        return True

    def refresh(self):
        if not self.require_client() or self.refreshing:
            return
        self.refreshing = True
        self.last_refresh = time.monotonic()
        def done(torrents):
            self.refreshing = False
            if torrents is None:
                self.connected = False
                return
            self.torrents = {t["hash"]: t for t in torrents}
            for item in self.downloads.get_children():
                if item not in self.torrents:
                    self.downloads.delete(item)
            for key, torrent in self.torrents.items():
                eta = torrent.get("eta", -1)
                row_values = (torrent["name"], f"{torrent.get('progress', 0)*100:.1f}%",
                          f"{count(torrent.get('num_seeds'))} / {count(torrent.get('num_complete'))}",
                          f"{count(torrent.get('num_leechs'))} / {count(torrent.get('num_incomplete'))}",
                          size(torrent.get("dlspeed", 0)) + "/s", size(torrent.get("upspeed", 0)) + "/s",
                          size(torrent.get("size", 0)),
                          "—" if eta < 0 or eta >= 8640000 else f"{eta // 60} minutes", torrent.get("state"))
                if self.downloads.exists(key):
                    self.downloads.item(key, values=row_values)
                else:
                    self.downloads.insert("", "end", iid=key, values=row_values)
            if self.download_shutdown.update(torrents, busy=(self.searching or self.batch_busy or
                                               bool(self.queued and self.wait_download.get()))):
                self.shutdown_qbit()
        self.run(lambda: self.client.torrents(), done)

    def shutdown_qbit(self):
        if self.shutting_down_qbit or not self.connected:
            return
        self.shutting_down_qbit = True
        self.connected = False
        self.qstatus.set("All observed downloads finished. Closing qBittorrent…")
        client = self.client
        def done(value):
            self.shutting_down_qbit = False
            if value:
                self.qstatus.set("qBittorrent is closing after downloads completed. Open Torrents to start it again.")
                self.app.status.set("qBittorrent is closing after downloads completed.")
        self.run(lambda: (client.shutdown(), True)[1], done)

    def show_peers(self):
        selected = self.downloads.selection()
        if not self.require_client() or not selected:
            return
        def done(data):
            if data is None:
                return
            window = tk.Toplevel(self.root)
            window.title("Peers for the selected torrent")
            window.geometry("950x420")
            view = table(window, [("ip", "IP", 180), ("port", "Port", 65), ("client", "Client", 180),
                                 ("progress", "%", 60), ("down", "Download", 100), ("up", "Upload", 100),
                                 ("flags", "Flags", 90)])
            for peer in (data.get("peers") or {}).values():
                view.insert("", "end", values=(peer.get("ip"), peer.get("port"), peer.get("client"),
                    f"{peer.get('progress',0)*100:.1f}", size(peer.get("dl_speed",0))+"/s",
                    size(peer.get("up_speed",0))+"/s", peer.get("flags")))
        self.run(lambda: self.client.peers(selected[0]), done)

    def search(self):
        if not self.require_client() or self.searching or not self.pattern.get().strip():
            return
        self.cancel_search = threading.Event()
        self.searching = True
        self.hits.clear()
        self.search_results.delete(*self.search_results.get_children())
        pattern, plugin = self.pattern.get().strip(), self.plugin.get()
        self.qstatus.set("Searching qBittorrent plugins…")
        def done(result):
            self.searching = False
            if result:
                self.qstatus.set(result + f" {len(self.hits)} results.")
        self.run(lambda: self.client.search(pattern, plugin, self.cancel_search,
                                           lambda result: self.events.put(("hit", result))), done)

    def add_selected(self):
        selected = self.search_results.selection()
        if selected:
            hit = self.hits[selected[0]]
            self.add(hit.get("fileUrl", ""), hit.get("fileName", "Torrent"))

    def add_magnet(self):
        if self.magnet.get().strip():
            self.add(self.magnet.get().strip(), "Torrent from magnet / URL")

    def add_torrent_file(self):
        if not self.require_client():
            return
        path = filedialog.askopenfilename(filetypes=[("Torrent", "*.torrent")])
        if path:
            self.add(path, Path(path).name, local=True)

    def add(self, reference, name, local=False):
        if not self.require_client():
            return
        folder = self.app.settings.get('library_root') or filedialog.askdirectory(title="Choose torrent save folder")
        if not folder:
            return
        if not messagebox.askyesno("Start torrent download", f"{name}\n\nSave to: {folder}\n\nAdd this torrent to qBittorrent?"):
            return
        def job():
            if local:
                self.client.add_file(reference, folder)
            else:
                self.client.add_url(reference, folder)
            return True
        def done(ok):
            if ok:
                self.download_shutdown.added()
                self.qstatus.set("Torrent added. Select it in Downloads to find subtitles.")
                self.refresh()
        self.run(job, done)

    def subtitle_from_hit(self):
        selected = self.search_results.selection()
        if selected:
            self.app.apply_movie(identify(Path(self.hits[selected[0]]["fileName"])))
            self.app.vars["movie"].set("")
            self.app.show_tools(self.app.workflow)
            self.app.status.set("Search by torrent name; file metadata is needed to match episodes.")

    def import_torrent(self):
        selected = self.downloads.selection()
        if not self.require_client() or not selected or self.batch_busy:
            return
        torrent_hash = selected[0]
        self.batch_busy = True
        def job():
            torrents = self.client.torrents(torrent_hash)
            if not torrents:
                raise QbitError("The torrent is no longer in qBittorrent.")
            torrent = torrents[0]
            rows = []
            for file in self.client.files(torrent_hash):
                if file.get("priority", 1) == 0:
                    continue
                path = content_file(torrent, file)
                if path.suffix.lower() not in VIDEO_EXTENSIONS:
                    continue
                movie = identify(path)
                progress = file.get("progress", 0)
                found = existing_subtitle(path) if path.parent.exists() else None
                rows.append(Episode(path, movie, not bool(found),
                     "Subtitle exists" if found else "Not searched", torrent_hash=torrent_hash,
                     file_index=file["index"], progress=progress))
            return rows
        def done(rows):
            self.batch_busy = False
            if rows is not None:
                self.set_rows(rows)
                self.app.show_subtitles()
                self.bstatus.set("File list imported. If empty, wait for torrent metadata and try again.")
        self.run(job, done)

    def build_batch(self):
        row = ttk.Frame(self.btab)
        row.pack(fill="x")
        ttk.Button(row, text="Choose series folder…", command=self.scan).pack(side="left")
        self.recursive = tk.BooleanVar(value=True)
        ttk.Checkbutton(row, text="Include subfolders", variable=self.recursive).pack(side="left", padx=6)
        self.title = tk.StringVar()
        self.season = tk.StringVar()
        self.language = tk.StringVar(value="vi")
        row = ttk.Frame(self.btab)
        row.pack(fill="x", pady=8)
        for label, var, width in (("Series title override", self.title, 30),
                                  ("Season", self.season, 5), ("Languages", self.language, 6)):
            ttk.Label(row, text=label).pack(side="left", padx=4)
            ttk.Entry(row, textvariable=var, width=width).pack(side="left", fill="x", expand=width == 30)
        ttk.Button(row, text="Apply title / season", command=self.apply_common).pack(side="left", padx=4)
        self.batch_table = table(self.btab, [("use", "Chọn", 45), ("file", "Video filename", 260),
             ("title", "Series title", 160), ("season", "Season", 45), ("episode", "Episode", 45),
             ("progress", "Video progress", 65), ("sub", "Selected subtitle", 220), ("state", "Status", 250)])
        self.batch_table.bind("<Double-1>", lambda e: self.edit())
        row = ttk.Frame(self.btab)
        row.pack(fill="x", pady=4)
        for label, command in (("Toggle row", self.toggle), ("Edit episode…", self.edit),
            ("Find subtitles for all files", self.search_batch), ("Choose another version…", self.choose_result),
            ("Download selected subtitles", self.download_batch), ("Cancel", self.cancel_batch_work)):
            ttk.Button(row, text=label, command=command).pack(side="left", padx=2)
        self.wait_download = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.btab, text="Apply prepared subtitles when videos finish downloading",
                        variable=self.wait_download).pack(anchor="w", pady=5)
        ttk.Button(self.btab, text="Open selected episode with subtitles", command=self.open_episode).pack(anchor="w")
        ttk.Label(self.btab, text="Save next to the video with the same filename. Skip existing subtitles. "
                  "Double-click a row to edit its details without renaming the video.",
                  wraplength=1000, style="Hint.TLabel").pack(anchor="w")
        self.bstatus = tk.StringVar(value="Choose a folder or import a torrent from qBittorrent.")
        ttk.Label(self.btab, textvariable=self.bstatus, wraplength=1000).pack(anchor="w", pady=5)

    def set_rows(self, rows):
        self.rows = rows
        self.queued.clear()
        self.cache = None
        self.prepared.clear()
        self.redraw()

    def redraw(self):
        chosen = self.batch_table.selection()
        self.batch_table.delete(*self.batch_table.get_children())
        for index, row in enumerate(self.rows):
            self.batch_table.insert("", "end", iid=str(index), values=(
                "✓" if row.enabled else "", row.path.name, row.movie.title, row.movie.season,
                row.movie.episode, f"{row.progress*100:.0f}%",
                f"{row.selected.provider}: {row.selected.release}" if row.selected else "", row.state))
        kept = [item for item in chosen if self.batch_table.exists(item)]
        if kept:
            self.batch_table.selection_set(kept)

    def scan(self):
        if self.batch_busy:
            return
        folder = filedialog.askdirectory(title="Choose series folder")
        if folder:
            recursive = self.recursive.get()
            title, season = self.title.get().strip(), self.season.get().strip()
            if season and not season.isdecimal():
                self.bstatus.set("Season must be numeric.")
                return
            self.batch_busy = True
            def done(rows):
                self.batch_busy = False
                if rows is not None:
                    self.set_rows(rows)
                    self.bstatus.set(f"Scanned {len(rows)} episodes. Check their titles and season/episode before searching.")
            self.run(lambda: scan_folder(folder, recursive, title, season), done)

    def selected_row(self):
        selected = self.batch_table.selection()
        focused = self.batch_table.focus()
        return int(focused if focused in selected else selected[0]) if selected else None

    def toggle(self):
        index = self.selected_row()
        if index is not None and not self.batch_busy:
            self.rows[index].enabled = not self.rows[index].enabled
            self.queued.discard(index)
            self.redraw()

    def apply_common(self):
        if self.batch_busy:
            return
        title, season = self.title.get().strip(), self.season.get().strip()
        if season and not season.isdecimal():
            self.bstatus.set("Season must be numeric.")
            return
        for row in self.rows:
            if row.enabled:
                row.movie = replace(row.movie, title=title or row.movie.title,
                                    season=str(int(season)) if season else row.movie.season)
                row.selected = None
                row.candidates = []
                row.state = "Not searched"
        self.queued.clear()
        self.redraw()

    def edit(self):
        index = self.selected_row()
        if index is None or self.batch_busy:
            return
        row = self.rows[index]
        window = tk.Toplevel(self.root)
        window.title("Edit episode details — video filename stays unchanged")
        variables = {}
        for field, label in (("title", "Series title"), ("year", "Year"), ("season", "Season"), ("episode", "Episode")):
            ttk.Label(window, text=label).pack(anchor="w", padx=12)
            variables[field] = tk.StringVar(value=getattr(row.movie, field))
            ttk.Entry(window, textvariable=variables[field], width=50).pack(padx=12, pady=4)
        def save():
            if self.batch_busy:
                return
            values = {k: v.get().strip() for k, v in variables.items()}
            if not values["title"] or any(not values[k].isdecimal() for k in ("season", "episode")):
                messagebox.showinfo("Episode details", "Enter a title and numeric season/episode.", parent=window)
                return
            values["season"], values["episode"] = str(int(values["season"])), str(int(values["episode"]))
            row.movie = replace(row.movie, **values)
            row.selected, row.candidates, row.state = None, [], "Not searched"
            self.queued.discard(index)
            self.redraw()
            window.destroy()
        ttk.Button(window, text="Save details", command=save).pack(pady=10)

    def search_batch(self):
        if self.batch_busy or not self.rows:
            return
        ids = [k for k, v in self.app.enabled.items() if v.get()]
        if not ids:
            self.bstatus.set("Enable a source and enter its API key in Settings.")
            return
        language = self.language.get().strip().lower()
        if not language or not all(c.isalpha() or c == "-" for c in language):
            self.bstatus.set("Enter a language code such as vi or en.")
            return
        self.cancel_batch = threading.Event()
        self.batch_busy = True
        self.queued.clear()
        def job():
            for index, original in enumerate(self.rows):
                if self.cancel_batch.is_set():
                    break
                if not original.enabled:
                    continue
                row = replace(original, candidates=[], selected=None)
                if not row.movie.season.isdecimal() or not row.movie.episode.isdecimal():
                    row.state = "Edit season/episode"
                else:
                    row.state = "Searching…"
                    self.events.put(("row", index, replace(row)))
                    found, errors = [], []
                    def emit(kind, key, value):
                        if kind == "result":
                            score = rank(row.movie, value, language)
                            if score is not None:
                                found.append((score, value))
                        elif kind == "error":
                            errors.append(f"{key}: {value}")
                    self.app.engine.run(Query(row.movie, (language,)), ids, self.cancel_batch, emit)
                    found.sort(key=lambda x: x[0], reverse=True)
                    row.candidates = found
                    if self.cancel_batch.is_set():
                        row.state = "Cancelled"
                    elif found:
                        if found[0][0] >= 75 and (len(found) == 1 or found[0][0] - found[1][0] >= 5):
                            row.selected = found[0][1]
                            row.state = "Matched — review before downloading"
                        else:
                            row.state = "Choose a subtitle"
                    else:
                        row.state = "; ".join(errors) or "No confirmed episode match"
                self.events.put(("row", index, row))
            return True
        def done(value):
            self.batch_busy = False
            self.bstatus.set("Search finished. Choose a version for each file, then download.")
        self.run(job, done)

    def choose_result(self):
        index = self.selected_row()
        if index is None or self.batch_busy:
            return
        row = self.rows[index]
        if not row.candidates:
            self.bstatus.set("No confirmed episode result for this row. Edit its details or search again.")
            return
        window = tk.Toplevel(self.root)
        window.title(f"Choose subtitle • {row.path.name}")
        window.geometry("1000x400")
        view = table(window, [("source", "Source", 110), ("release", "Release", 500),
                             ("author", "Uploader", 150), ("score", "Match", 70)])
        for i, (score, result) in enumerate(row.candidates):
            view.insert("", "end", iid=str(i), values=(result.provider, result.release, result.uploader, score))
        ttk.Label(window, text="Only matching language and season/episode results or season packs are shown. Scores reflect title "
                  "and release similarity; episode filenames inside season packs still need checking. Synchronization is not guaranteed.",
                  wraplength=950).pack(padx=8)
        def choose():
            selection = view.selection()
            if selection and not self.batch_busy:
                row.selected = row.candidates[int(selection[0])][1]
                row.state = "Selected"
                self.queued.discard(index)
                self.redraw()
                window.destroy()
        ttk.Button(window, text="Use this subtitle", command=choose).pack(pady=6)
        view.bind("<Double-1>", lambda e: choose())

    def resolve_torrent_row(self, row):
        if not row.torrent_hash:
            return row
        if not self.connected:
            raise QbitError("Connect to qBittorrent to verify the current file.")
        torrents = self.client.torrents(row.torrent_hash)
        if not torrents:
            raise QbitError("The torrent was removed; subtitle was not applied.")
        file = next((f for f in self.client.files(row.torrent_hash) if f["index"] == row.file_index), None)
        if file is None or file.get("priority", 1) == 0:
            raise QbitError("This file was deselected or removed from the torrent; subtitle was not applied.")
        path = content_file(torrents[0], file)
        if path.name != row.path.name:
            raise QbitError("Torrent filename changed; import the file list and match subtitles again.")
        return replace(row, path=path, progress=file.get("progress", 0))

    def open_episode(self):
        index = self.selected_row()
        if index is None or self.batch_busy:
            return
        row = self.rows[index]
        try:
            row = self.resolve_torrent_row(row)
            if row.progress < 1 or not row.path.is_file():
                raise ValueError("Wait for the video to finish downloading before opening it.")
            subtitle = row.path.with_suffix(Path(row.saved).suffix) if row.saved else existing_subtitle(row.path)
            if subtitle is None or not subtitle.is_file():
                raise ValueError("No saved subtitle for this episode.")
            from .players import launch
            launch(self.app.player_kind.get(), self.app.player_path.get(), str(row.path), str(subtitle))
            self.bstatus.set("Opened the episode with subtitles. The player may restart playback.")
        except Exception as exc:
            self.bstatus.set(str(exc) if isinstance(exc, (ValueError, QbitError)) else error_text(exc))

    def process_subtitle(self, row, index, encoding):
        """Prepare/apply one chosen result; safe to call from either worker flow."""
        row = self.resolve_torrent_row(row)
        if row.path.parent.exists() and existing_subtitle(row.path):
            return replace(row, state="Existing subtitle — skipped"), False
        result = row.selected
        key = (result.provider, result.id)
        prepared_key = (index, *key)
        if prepared_key not in self.prepared:
            if self.cache is None or self.cache[0] != key:
                context = Context(self.cancel_batch, time.monotonic() +
                                  self.app.registry.providers[result.provider].capabilities.timeout)
                name, data = self.app.engine.download(result, context)
                self.cache = (key, unpack_subtitles(name, data))
            name, data = select_file(row.movie, result, self.cache[1])
            decode_subtitle(data, encoding)
            self.prepared[prepared_key] = (name, data)
        if self.cancel_batch.is_set():
            raise ValueError("Cancelled")
        name, data = self.prepared[prepared_key]
        row = self.resolve_torrent_row(row)
        if self.cancel_batch.is_set():
            raise ValueError("Cancelled")
        if row.progress < 1:
            return replace(row, state="Subtitle downloaded; waiting for video"), True
        path = save_episode(row, name, data, encoding)
        prefix = "Auto-saved: " if index in getattr(self, "automatic_rows", set()) else "Saved: "
        return replace(row, state=prefix + result.provider if path else "Existing subtitle — skipped",
                       saved=str(path or "")), False

    def download_batch(self, automatic=False, indices=None):
        if self.batch_busy:
            return
        if indices is None:
            indices = list(self.queued) if automatic else [i for i, r in enumerate(self.rows) if r.enabled and r.selected]
        if not indices:
            if not automatic:
                self.bstatus.set("No episodes have a selected subtitle.")
            return
        self.cancel_batch = threading.Event()
        self.batch_busy = True
        encoding = self.app.encoding.get()
        def job():
            for index in indices:
                if self.cancel_batch.is_set():
                    break
                row = replace(self.rows[index])
                if not row.enabled or not row.selected:
                    continue
                waiting = False
                try:
                    row, waiting = self.process_subtitle(row, index, encoding)
                except Exception as exc:
                    row.state = str(exc) if isinstance(exc, (ValueError, QbitError)) else error_text(exc)
                self.events.put(("saved", index, row, waiting))
            return True
        def done(value):
            self.batch_busy = False
            self.last_batch = time.monotonic()
            self.bstatus.set("Download pass finished. Check each file; downloaded subtitles will apply when videos finish.")
        self.run(job, done)

    def cancel_batch_work(self):
        self.cancel_batch.set()
        self.queued.clear()
        self.bstatus.set("Cancelled. Saved subtitles are retained; choose a subtitle again to resume.")

    def poll(self):
        if self.stopped:
            return
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if event[0] == "callback":
                if event[1]:
                    event[1](event[2])
            elif event[0] == "error":
                self.qstatus.set(event[1])
                self.bstatus.set(event[1])
            elif event[0] == "hit":
                value = event[1]
                key = str(len(self.hits))
                self.hits[key] = value
                self.search_results.insert("", "end", iid=key, values=(value.get("fileName"),
                    size(value.get("fileSize", -1)), count(value.get("nbSeeders")), count(value.get("nbLeechers")),
                    value.get("siteUrl")))
            elif event[0] in ("row", "saved"):
                _, index, row, *waiting = event
                self.rows[index] = row
                if waiting:
                    if waiting[0] and not self.cancel_batch.is_set():
                        self.queued.add(index)
                    else:
                        self.queued.discard(index)
                self.redraw()
        now = time.monotonic()
        if self.connected and now - self.last_refresh > 5:
            self.refresh()
        if self.connected and self.queued and self.wait_download.get() and not self.batch_busy and now - self.last_batch > 10:
            self.download_batch(automatic=True)
        self.root.after(150, self.poll)

    def close(self):
        self.stopped = True
        self.cancel_search.set()
        self.cancel_batch.set()
        self.persist()
