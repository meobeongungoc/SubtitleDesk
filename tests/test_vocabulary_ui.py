"""Exercise the real worker, preview, selected folder and GUI export flow."""
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from subtitledesk.gui import Application


class VocabularyUITests(unittest.TestCase):
    def test_scan_preview_export_and_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            movie = home/'Selected series';movie.mkdir()
            sub = movie/'Episode.S01E01.en.srt'
            sub.write_text('1\n00:00:01,000 --> 00:00:03,000\nWe scrutinize a meticulous protagonist.\n', 'utf-8')
            app = Application(home)
            try:
                library = app.library
                library.library_folders = {'Selected series': movie}
                library.movie_choice.set('Selected series')
                library.show_vocabulary()
                dialog = library.vocabulary_window
                self.assertEqual(Path(dialog.folder.get()), movie)
                library.show_vocabulary()
                self.assertIs(library.vocabulary_window, dialog)
                dialog.scan()
                deadline = time.monotonic() + 6
                while dialog.busy and time.monotonic() < deadline:
                    app.root.update()
                    time.sleep(.01)
                self.assertFalse(dialog.busy)
                self.assertIsNotNone(dialog.report)
                self.assertIn('meticulous', {card.term for card in dialog.report.cards})
                self.assertEqual(len(dialog.table.get_children()), len(dialog.report.cards))
                self.assertEqual(str(dialog.export_button.cget('state')), 'normal')
                output = home/'Test-Anki.txt'
                with patch('subtitledesk.vocabulary_ui.filedialog.asksaveasfilename', return_value=str(output)):
                    dialog.export()
                    self.assertTrue(output.read_text('utf-8').startswith('#separator:Tab'))
                    before = output.read_bytes()
                    dialog.export()
                    self.assertIn('already exists', dialog.status.get())
                    self.assertEqual(before, output.read_bytes())
                app.theme_manager.apply('purple')
                app.root.update()
                self.assertEqual(dialog.window.cget('background'), '#131320')
                dialog.levels.set('C2')
                self.assertIsNone(dialog.report)
                self.assertEqual(str(dialog.export_button.cget('state')), 'disabled')
                dialog.close()
                library.show_vocabulary()
                self.assertIsNot(library.vocabulary_window, dialog)
                # Closing the whole app while this window is alive must release
                # its timer and stop the worker without double-deleting Tcl callbacks.
                library.vocabulary_window.scan()
            finally:
                app.close()
            self.assertTrue(library.vocabulary_window.cancel.is_set())


if __name__ == '__main__':
    unittest.main()
