"""Movie-list actions keep Explorer-like selection and preserve subtitle files."""
from pathlib import Path
import tempfile
import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from subtitledesk.batch import scan_folder
from subtitledesk.gui import Application
from subtitledesk.players import MpcBe


class MovieInteractionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.home = Path(self.directory.name).resolve()
        self.videos = [self.home / f"Show.S01E{i:02d}.mkv" for i in (1, 2, 3)]
        for path in self.videos:
            path.write_bytes(b"Disposable UI fixture")
        self.error_dialog = patch("subtitledesk.simple_ui.messagebox.showerror", side_effect=AssertionError("Unexpected error dialog"))
        self.error_dialog.start()
        self.addCleanup(self.error_dialog.stop)
        self.app = Application(self.home)
        self.app.root.withdraw()
        self.library = self.app.library
        self.app.settings["library_root"] = str(self.home)
        self.library.set_rows(scan_folder(self.home))

    def tearDown(self):
        self.app.close()
        self.directory.cleanup()

    def test_open_without_subtitle_and_exact_saved_language_path(self):
        library = self.library
        library.batch_table.selection_set("1")
        library.batch_table.focus("1")
        with patch("subtitledesk.players.launch") as launch:
            library.open_movie()
            self.assertEqual(launch.call_args.args[2:], (str(self.videos[1]), None))
            subtitle = self.videos[1].with_suffix(".vi.srt")
            subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nExample\n", encoding="utf-8")
            library.rows[1].saved = str(subtitle)
            library.redraw()
            library.open_movie()
            self.assertEqual(launch.call_args.args[3], str(subtitle))
            library.rows[1].progress = .5
            library.open_movie()
            self.assertEqual(launch.call_count, 2)
            self.assertIn("finish downloading", library.bstatus.get())
        command = MpcBe().command(Path("player.exe"), self.videos[0])
        self.assertEqual(len(command), 2)
        self.assertNotIn("/sub", command)

    def test_context_selection_and_redraw_preserve_focused_episode(self):
        library = self.library
        view = library.batch_table
        view.selection_set(("0", "2"))
        event = SimpleNamespace(y=10, x_root=100, y_root=100)
        with patch.object(view, "identify_row", return_value="2"), \
                patch.object(library.movie_menu, "tk_popup"), \
                patch.object(library.movie_menu, "grab_release"):
            library.show_movie_menu(event)
            self.assertEqual(view.selection(), ("0", "2"))
            self.assertEqual(view.focus(), "2")
            library.redraw()
            self.assertEqual(view.selection(), ("0", "2"))
            self.assertEqual(library.selected_row(), 2)
        with patch.object(view, "identify_row", return_value="1"), \
                patch.object(library.movie_menu, "tk_popup"), \
                patch.object(library.movie_menu, "grab_release"):
            library.show_movie_menu(event)
            self.assertEqual(view.selection(), ("1",))
        library.select_all_movies()
        self.assertEqual(len(view.selection()), 3)

    def test_delete_menu_cancels_blocks_busy_and_recycles_only_selected_videos(self):
        library = self.library
        subtitle = self.videos[0].with_suffix(".srt")
        subtitle.write_text("Subtitle must stay", encoding="utf-8")
        library.batch_table.selection_set(("0", "2"))
        with patch("subtitledesk.simple_ui.messagebox.askyesno", return_value=False):
            library.movie_menu.invoke("Delete")
        self.assertTrue(all(path.exists() for path in self.videos))
        with patch("subtitledesk.simple_ui.messagebox.askyesno", return_value=True) as confirm:
            library.batch_busy = True
            library.recycle_selected_movies()
            confirm.assert_not_called()
            library.batch_busy = False
            library.rows[0].torrent_hash = "fixture"
            with patch("subtitledesk.simple_ui.messagebox.showwarning") as warning:
                library.recycle_selected_movies()
                warning.assert_called_once()
            confirm.assert_not_called()
            library.rows[0].torrent_hash = ""
            library.movie_menu.invoke("Delete")
            confirm.assert_called_once()
        self.assertFalse(self.videos[0].exists())
        self.assertTrue(self.videos[1].exists())
        self.assertFalse(self.videos[2].exists())
        self.assertTrue(subtitle.exists())
        self.assertEqual([row.path for row in library.rows], [self.videos[1]])


if __name__ == "__main__":
    unittest.main()
