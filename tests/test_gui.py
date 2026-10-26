"""Exercises our own widgets, callbacks and file workflow, not external app UI."""
import tempfile
import unittest
import time
import tkinter as tk
from pathlib import Path
from unittest.mock import patch, Mock
from subtitledesk.gui import Application
from subtitledesk.bridge import enqueue
from test_core import SRT, archive


class GuiTests(unittest.TestCase):


    def test_batch_search_save_pack_once_and_open(self):
        from subtitledesk.providers import Registry, Capabilities, Page, Result, SearchEngine
        from subtitledesk.batch import scan_folder
        class PackSource:
            capabilities = Capabilities("fixture", "Fixture", min_interval=0)
            downloads = 0
            def search(self, query, cursor, context):
                return Page([Result("fixture", "pack", "Show", "vi", "Show.S01",
                                    season="1", season_pack=True)])
            def download(self, result, context):
                self.downloads += 1
                return "pack.zip", archive([(f"Show.S01E{e:02d}.srt", SRT) for e in (1, 2, 3)])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for episode in (1, 2):
                (root / f"Show.S01E{episode:02d}.mkv").write_bytes(b"fixture-video")
            app = Application(root)
            app.root.withdraw()
            try:
                source = PackSource()
                app.registry = Registry()
                app.registry.add(source)
                app.engine = SearchEngine(app.registry)
                app.enabled = {"fixture": tk.BooleanVar(master=app.root, value=True)}
                library = app.library
                library.set_rows(scan_folder(root))
                def wait():
                    deadline = time.monotonic() + 8
                    while library.batch_busy and time.monotonic() < deadline:
                        app.root.update()
                        time.sleep(.01)
                    self.assertFalse(library.batch_busy)
                library.search_batch()
                wait()
                self.assertTrue(all(r.selected is None for r in library.rows))
                for row in library.rows:
                    row.selected = row.candidates[0][1]
                library.download_batch()
                wait()
                self.assertEqual(source.downloads, 1)
                self.assertTrue(all(r.state.startswith("Saved:") for r in library.rows))
                self.assertEqual((root / "Show.S01E02.vi.srt").read_bytes(), SRT)
                library.batch_table.selection_set("1")
                with patch("subtitledesk.players.launch") as launch:
                    library.open_episode()
                    self.assertEqual(Path(launch.call_args.args[3]).resolve(), (root / "Show.S01E02.vi.srt").resolve())
                library.download_batch()
                wait()
                self.assertEqual(source.downloads, 1)
            finally:
                app.close()

    def test_local_workflow_browser_and_save_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = Application(root)
            app.root.withdraw()
            try:
                app.root.update()
                self.assertIsNotNone(app.dnd_type)
                movie = root / "Phim.Viet.2024.S01E02.mkv"
                movie.write_bytes(b"test-only-placeholder-not-playable")
                subtitle = root / "subtitle.srt"
                subtitle.write_bytes(SRT)
                app.set_movie(str(movie))
                self.assertEqual(app.vars["episode"].get(), "2")
                app.import_file(str(subtitle))
                self.assertEqual(app.selected_data, SRT)
                self.assertIn("Việt Nam", app.preview.get("1.0", "end"))
                output = root / "saved.srt"
                with patch("subtitledesk.gui.filedialog.asksaveasfilename", return_value=str(output)):
                    self.assertEqual(app.save(), str(output))
                    with patch("subtitledesk.gui.messagebox.askyesno", return_value=False) as prompt:
                        self.assertIsNone(app.save())
                        prompt.assert_not_called()
                        self.assertIsNotNone(app.pending_confirmation)
                        app.cancel_confirmation()
                self.assertEqual(output.read_bytes(), SRT)
                self.assertEqual(set(app.registry.providers), {"subdl", "opensubtitles"})
                for var in app.enabled.values():
                    var.set(False)
                app.search()
                self.assertIn("No sources enabled", app.status.get())
                self.assertEqual(len(app.library.panes.panes()), 3)
                from subtitledesk.batch import scan_folder
                app.library.set_rows(scan_folder(root))
                self.assertEqual(len(app.library.batch_table.get_children()), 1)
                app.library.batch_table.selection_set("0")
                app.library.toggle()
                self.assertFalse(app.library.rows[0].enabled)
                enqueue(root, {"action": "search", "url": "https://example.org/",
                               "title": "Browser Film 2025", "selection": ""})
                app.poll()
                self.assertEqual(len(app.browser_pending), 1)
                app.take_browser()
                self.assertEqual(app.vars["title"].get(), "Browser Film")
                self.assertEqual(app.vars["movie"].get(), "")
                self.assertFalse(list((root / "data" / "inbox").glob("*.pending")))
                app.persist(False)
                self.assertTrue((root / "data" / "settings.json").exists())
                self.assertEqual(movie.read_bytes(), b"test-only-placeholder-not-playable")
            finally:
                app.close()
