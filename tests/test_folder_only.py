"""Folder-only regression checks, including inert legacy queue migration."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from subtitledesk.gui import Application
from subtitledesk.storage import load_settings


class FolderOnlyTests(unittest.TestCase):
    def test_old_settings_and_pending_cache_never_reconnect_or_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve()
            movies = home / "Movies"
            movies.mkdir()
            video = movies / "Show.S01E01.mkv"
            video.write_bytes(b"Local movie fixture")
            data = home / "data"
            data.mkdir()
            legacy = {"theme": "green", "library_root": str(movies), "languages": "en",
                      "qbit_auto": True, "qbit_url": "http://127.0.0.1:1"}
            (data / "settings.json").write_text(json.dumps(legacy), encoding="utf-8")
            queue = data / "pending-subtitles.json"
            queue.write_text('[{"torrent_hash":"obsolete-fixture"}]', encoding="utf-8")
            cache = data / "pending"
            cache.mkdir()
            cached = cache / "fixture.srt"
            cached.write_bytes(b"Preserve old cached subtitle")
            original = queue.read_bytes(), cached.read_bytes()
            app = Application(home)
            app.root.withdraw()
            try:
                self.assertEqual(app.theme_key, "green")
                self.assertEqual(app.language.get(), "en")
                self.assertFalse(any(k.startswith("qbit") for k in app.settings))
                self.assertFalse(hasattr(app, "torrent_window"))
                self.assertFalse(hasattr(app, "show_torrents"))
                self.assertFalse(hasattr(app.library, "client"))
                self.assertFalse(hasattr(app.library, "restore_pending"))
                self.assertNotIn("subtitledesk.qbittorrent", sys.modules)
                # Run discovery and folder loading through their real callbacks synchronously.
                app.library.run = lambda job, done, **kwargs: done(job())
                with patch.object(app.engine, "download", side_effect=AssertionError("Unexpected old queue download")):
                    app.library.refresh_library()
                    app.library.poll()
                self.assertEqual([r.path for r in app.library.rows], [video])
                self.assertEqual(queue.read_bytes(), original[0])
                self.assertEqual(cached.read_bytes(), original[1])
                self.assertFalse(video.with_suffix(".srt").exists())
                texts = []
                def walk(widget):
                    if "text" in widget.keys():
                        texts.append(str(widget.cget("text")))
                    for child in widget.winfo_children():
                        walk(child)
                walk(app.root)
                self.assertFalse(any("torrent" in text.lower() for text in texts))
                app.persist(False)
                settings = load_settings(data)
                self.assertEqual(settings["library_root"], str(movies))
                self.assertEqual(settings["theme"], "green")
            finally:
                app.close()

    def test_refresh_rescans_current_folder_and_clears_removed_library(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve()
            movies = home / "Movies"
            movies.mkdir()
            first = movies / "Show.S01E01.mkv"
            first.write_bytes(b"Fixture one")
            app = Application(home)
            app.root.withdraw()
            try:
                library = app.library
                app.settings["library_root"] = str(movies)
                library.run = lambda job, done, **kwargs: done(job())
                library.refresh_library()
                self.assertEqual(len(library.rows), 1)
                second = movies / "Show.S01E02.mkv"
                second.write_bytes(b"Fixture two")
                library.refresh_library()
                self.assertEqual([r.path for r in library.rows], [first, second])
                first.unlink()
                second.unlink()
                library.refresh_library()
                self.assertEqual(library.rows, [])
                self.assertEqual(library.movie_picker.cget("values"), "")
            finally:
                app.close()
