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

    def show_without_focus(self):
        import ctypes
        root = self.app.root
        root.geometry("1200x700+20000+20000")
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        ctypes.windll.user32.ShowWindow(hwnd, 4)  # SW_SHOWNOACTIVATE
        root.update()

    def test_row_buttons_target_only_their_episode(self):
        self.show_without_focus()
        library = self.library
        view = library.batch_table
        self.assertIn("1", library.movie_actions.buttons)
        play, delete = library.movie_actions.buttons["1"]
        self.assertTrue(play.winfo_ismapped())
        self.assertTrue(delete.winfo_ismapped())
        view.selection_set(("0", "2"))
        with patch("subtitledesk.players.launch") as launch:
            play.invoke()
            self.assertEqual(launch.call_args.args[2], str(self.videos[1]))
        subtitle = self.videos[1].with_suffix(".srt")
        subtitle.write_text("Keep this subtitle", encoding="utf-8")
        view.selection_set(("0", "2"))
        with patch("subtitledesk.simple_ui.messagebox.askyesno",
                   side_effect=AssertionError("No confirmation allowed")):
            # Exercise the real ttk mouse bindings, not just the Python callback.
            delete.event_generate("<Enter>")
            delete.event_generate("<ButtonPress-1>", x=5, y=5)
            delete.event_generate("<ButtonRelease-1>", x=5, y=5)
            self.app.root.update()
        self.assertFalse(self.videos[1].exists())
        self.assertTrue(self.videos[0].exists())
        self.assertTrue(self.videos[2].exists())
        self.assertTrue(subtitle.exists())
        self.assertEqual([r.path for r in library.rows], [self.videos[0], self.videos[2]])

    def test_row_buttons_follow_scroll_sort_resize_and_themes(self):
        from subtitledesk.library_ui import sort_table
        for i in range(4, 65):
            (self.home / f"Show.S01E{i:02d}.mkv").write_bytes(b"Disposable UI fixture")
        self.library.set_rows(scan_folder(self.home))
        self.show_without_focus()
        view = self.library.batch_table
        for theme in ("blue", "warm", "green", "purple"):
            self.app.theme_manager.apply(theme)
            self.app.root.geometry("1000x600+20000+20000")
            self.app.root.update()
            view.yview_moveto(1)
            self.app.root.update()
            actions = self.library.movie_actions
            self.assertIn("63", actions.buttons)
            self.assertNotIn("0", actions.buttons)
            self.assertLess(len(actions.buttons), 64)
            for item, buttons in actions.buttons.items():
                for column, button in zip(("play", "delete"), buttons):
                    x, y, width, height = view.bbox(item, column)
                    self.assertTrue(button.winfo_ismapped())
                    self.assertEqual(button.winfo_y(), y + 1)
                    self.assertGreaterEqual(button.winfo_width(), button.winfo_reqwidth())
        sort_table(view, "file")
        view.yview_moveto(0)
        self.app.root.update()
        first = view.get_children()[0]
        self.assertIn(first, self.library.movie_actions.buttons)
        with patch("subtitledesk.players.launch") as launch:
            self.library.movie_actions.buttons[first][0].invoke()
            self.assertEqual(launch.call_args.args[2], str(self.library.rows[int(first)].path))

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
            self.videos[1].unlink()
            library.open_movie()
            self.assertEqual(launch.call_count, 2)
            self.assertIn("no longer available", library.bstatus.get())
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

    def test_delete_without_confirmation_blocks_busy_and_keeps_subtitles(self):
        library = self.library
        subtitle = self.videos[0].with_suffix(".srt")
        subtitle.write_text("Subtitle must stay", encoding="utf-8")
        library.batch_table.selection_set(("0", "2"))
        with patch("subtitledesk.simple_ui.messagebox.askyesno", side_effect=AssertionError("Delete must not ask for confirmation")) as confirm:
            library.batch_busy = True
            library.recycle_selected_movies()
            confirm.assert_not_called()
            library.batch_busy = False
            library.movie_menu.invoke("Delete")
            confirm.assert_not_called()
        self.assertFalse(self.videos[0].exists())
        self.assertTrue(self.videos[1].exists())
        self.assertFalse(self.videos[2].exists())
        self.assertTrue(subtitle.exists())
        self.assertEqual([row.path for row in library.rows], [self.videos[1]])


if __name__ == "__main__":
    unittest.main()
