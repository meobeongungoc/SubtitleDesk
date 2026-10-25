from dataclasses import replace
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from .batch import select_file, save_episode, existing_subtitle
from .core import unpack_subtitles, decode_subtitle
from .providers import Context
from .sources import error_text


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
        self.cancel_batch = threading.Event()
        self.batch_busy = False
        self.rows = []
        self.cache = None
        self.prepared = {}
        self.stopped = False
        self.btab = ttk.Frame(app.main_content)
        self.btab.pack(fill="both", expand=True)
        self.build_batch()
        self.root.after(250, self.poll)

    def run(self, function, callback=None):
        def worker():
            try:
                value = function()
                self.events.put(("callback", callback, value))
            except Exception as exc:
                text = str(exc) if isinstance(exc, ValueError) else error_text(exc)
                self.events.put(("error", text))
                self.events.put(("callback", callback, None))
        threading.Thread(target=worker, daemon=True).start()

    def set_rows(self, rows):
        self.rows = rows
        self.cache = None
        self.prepared.clear()
        self.redraw()

    def redraw(self):
        chosen = self.batch_table.selection()
        focused = self.batch_table.focus()
        self.batch_table.delete(*self.batch_table.get_children())
        for index, row in enumerate(self.rows):
            self.batch_table.insert("", "end", iid=str(index), values=(
                "✓" if row.enabled else "", row.path.name, row.movie.title, row.movie.season,
                row.movie.episode,
                f"{row.selected.provider}: {row.selected.release}" if row.selected else "", row.state))
        kept = [item for item in chosen if self.batch_table.exists(item)]
        if kept:
            self.batch_table.selection_set(kept)
        if focused and self.batch_table.exists(focused):
            self.batch_table.focus(focused)

    def selected_row(self):
        selected = self.batch_table.selection()
        focused = self.batch_table.focus()
        return int(focused if focused in selected else selected[0]) if selected else None

    def toggle(self):
        index = self.selected_row()
        if index is not None and not self.batch_busy:
            self.rows[index].enabled = not self.rows[index].enabled
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
            self.redraw()
            window.destroy()
        ttk.Button(window, text="Save details", command=save).pack(pady=10)

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
                self.redraw()
                window.destroy()
        ttk.Button(window, text="Use this subtitle", command=choose).pack(pady=6)
        view.bind("<Double-1>", lambda e: choose())

    def open_episode(self):
        index = self.selected_row()
        if index is None or self.batch_busy:
            return
        row = self.rows[index]
        try:
            if not row.path.is_file():
                raise ValueError("The video file is no longer available. Refresh the movie library.")
            subtitle = Path(row.saved) if row.saved else None
            if subtitle is None or not subtitle.is_file():
                subtitle = existing_subtitle(row.path)
            from .players import launch
            launch(self.app.player_kind.get(), self.app.player_path.get(), str(row.path),
                   str(subtitle) if subtitle else None)
            self.bstatus.set("Opened the episode with subtitles. The player may restart playback."
                             if subtitle else "Opened the episode without an external subtitle.")
        except Exception as exc:
            self.bstatus.set(str(exc) if isinstance(exc, ValueError) else error_text(exc))

    def process_subtitle(self, row, index, encoding):
        """Prepare/apply one chosen result; safe to call from either worker flow."""
        if not row.path.is_file():
            raise ValueError("The video file is no longer available. Refresh the movie library.")
        if row.path.parent.exists() and existing_subtitle(row.path):
            return replace(row, state="Existing subtitle — skipped")
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
        if not row.path.is_file():
            raise ValueError("The video file is no longer available. Refresh the movie library.")
        if self.cancel_batch.is_set():
            raise ValueError("Cancelled")
        path = save_episode(row, name, data, encoding)
        prefix = "Auto-saved: " if index in getattr(self, "automatic_rows", set()) else "Saved: "
        return replace(row, state=prefix + result.provider if path else "Existing subtitle — skipped",
                       saved=str(path or ""))

    def download_batch(self, indices=None):
        if self.batch_busy:
            return
        if indices is None:
            indices = [i for i, r in enumerate(self.rows) if r.enabled and r.selected]
        if not indices:
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
                try:
                    row = self.process_subtitle(row, index, encoding)
                except Exception as exc:
                    row.state = str(exc) if isinstance(exc, ValueError) else error_text(exc)
                self.events.put(("saved", index, row))
            return True
        def done(value):
            self.batch_busy = False
            self.bstatus.set("Download finished. Check each file for the saved subtitle or any error.")
        self.run(job, done)

    def cancel_batch_work(self):
        self.cancel_batch.set()
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
                self.bstatus.set(event[1])
            elif event[0] in ("row", "saved"):
                _, index, row = event
                self.rows[index] = row
                self.redraw()
        self.root.after(150, self.poll)

    def close(self):
        self.stopped = True
        self.cancel_batch.set()
