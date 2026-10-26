"""Exercise the real worker, preview, selected folder and GUI export flow."""
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from subtitledesk.gui import Application
from subtitledesk.vocabulary import Card, Report
from subtitledesk.storage import dialog_directory


class VocabularyUITests(unittest.TestCase):
    def wait(self, app, dialog):
        deadline = time.monotonic() + 20
        while dialog.busy and time.monotonic() < deadline:
            app.root.update()
            time.sleep(.01)
        self.assertFalse(dialog.busy)

    def test_independent_dialog_folders_survive_restart_and_cancel(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            movie, chosen, output = (home/name for name in ('Movie library', 'Vocabulary input', 'Anki output'))
            for path in (movie, chosen, output):path.mkdir()
            app = Application(home)
            app.root.withdraw()
            try:
                app.settings['library_root'] = str(movie)
                app.library.current_folder = str(movie)
                app.library.show_vocabulary()
                dialog = app.library.vocabulary_window
                with patch('subtitledesk.vocabulary_ui.filedialog.askdirectory', return_value=str(chosen)) as picker:
                    dialog.browse()
                    self.assertEqual(Path(picker.call_args.kwargs['initialdir']), movie)
                self.assertEqual(Path(app.settings['vocabulary_input_dir']), chosen)
                self.assertEqual(Path(app.settings['library_root']), movie)
                dialog.report = Report(movie, cards=[Card('meticulous', 'C2', ('adjective',), count=1,
                    examples=[('A meticulous plan.', 'Episode.en.srt', '00:00:01,000')], files={'Episode.en.srt'})])
                with patch('subtitledesk.vocabulary_ui.filedialog.asksaveasfilename', return_value=str(output/'Cards.txt')) as picker:
                    dialog.export()
                    self.wait(app, dialog)
                    self.assertEqual(Path(picker.call_args.kwargs['initialdir']), movie)
                self.assertEqual(Path(app.settings['vocabulary_export_dir']), output)
                self.assertEqual(Path(app.settings['vocabulary_input_dir']), chosen)
                with patch('subtitledesk.simple_ui.filedialog.askdirectory', return_value='') as picker:
                    app.library.scan()
                    self.assertEqual(Path(picker.call_args.kwargs['initialdir']), movie)
            finally:
                app.close()
            resumed = Application(home)
            resumed.root.withdraw()
            try:
                resumed.library.show_vocabulary()
                dialog = resumed.library.vocabulary_window
                self.assertEqual(Path(dialog.folder.get()), chosen)
                with patch('subtitledesk.vocabulary_ui.filedialog.askdirectory', return_value='') as picker:
                    dialog.browse()
                    self.assertEqual(Path(picker.call_args.kwargs['initialdir']), chosen)
                    self.assertEqual(Path(resumed.settings['vocabulary_input_dir']), chosen)
                dialog.report = Report(movie, cards=[Card('meticulous', 'C2', ('adjective',), count=1,
                    examples=[('A meticulous plan.', 'Episode.en.srt', '00:00:01,000')], files={'Episode.en.srt'})])
                with patch('subtitledesk.vocabulary_ui.filedialog.asksaveasfilename', return_value='') as picker:
                    dialog.export()
                    self.wait(resumed, dialog)
                    self.assertEqual(Path(picker.call_args.kwargs['initialdir']), output)
                    self.assertEqual(Path(resumed.settings['vocabulary_export_dir']), output)
                self.assertEqual(Path(dialog_directory(output/'Deleted folder')), output)
            finally:
                resumed.close()

    def test_scan_preview_export_and_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            movie = home/'Selected series';movie.mkdir()
            sub = movie/'Episode.S01E01.en.srt'
            sub.write_text('1\n00:00:01,000 --> 00:00:03,000\nWe scrutinize a meticulous protagonist.\n', 'utf-8')
            app = Application(home)
            app.root.withdraw()
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
                deadline = time.monotonic() + 20
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
                    self.wait(app, dialog)
                    self.assertTrue(output.read_text('utf-8').startswith('#separator:Tab'))
                    self.assertFalse(sub.exists())
                    before = output.read_bytes()
                    dialog.export()
                    self.wait(app, dialog)
                    self.assertIn('already exists', dialog.status.get())
                    self.assertEqual(before, output.read_bytes())
                app.theme_manager.apply('purple')
                app.root.update()
                self.assertEqual(dialog.window.winfo_toplevel(), app.root)
                dialog.levels.set('C2')
                self.assertIsNone(dialog.report)
                self.assertEqual(str(dialog.export_button.cget('state')), 'disabled')
                dialog.close()
                library.show_vocabulary()
                self.assertIs(library.vocabulary_window, dialog)  # Embedded page preserves state.
                # Closing the whole app while this window is alive must release
                # its timer and stop the worker without double-deleting Tcl callbacks.
                library.vocabulary_window.scan()
            finally:
                app.close()
            self.assertTrue(library.vocabulary_window.cancel.is_set())

    def test_export_recycles_scanned_subtitles_only_after_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            movie = home/'Series'; movie.mkdir()
            english = movie/'Episode.en.srt'
            vietnamese = movie/'Episode.vi.srt'
            changed = movie/'Other.en.srt'
            dialogue = '1\n00:00:01,000 --> 00:00:03,000\nWe scrutinize a meticulous protagonist.\n'
            for path in (english, vietnamese, changed):
                path.write_text(dialogue, 'utf-8')
            app = Application(home)
            app.root.withdraw()
            try:
                app.library.show_vocabulary()
                dialog = app.library.vocabulary_window
                dialog.folder.set(str(movie))
                dialog.scan()
                deadline = time.monotonic() + 20
                while dialog.busy and time.monotonic() < deadline:
                    app.root.update()
                    time.sleep(.01)
                self.assertFalse(dialog.busy)
                self.assertTrue(dialog.report.cards)
                existing = home/'Already-exists.txt'
                existing.write_text('keep', 'utf-8')
                with patch('subtitledesk.vocabulary_ui.filedialog.asksaveasfilename', return_value=str(existing)):
                    dialog.export()
                    self.wait(app, dialog)
                self.assertTrue(all(path.exists() for path in (english, vietnamese, changed)))
                changed.write_text(dialogue + 'Changed after scanning.\n', 'utf-8')
                output = home/'New-export.txt'
                with patch('subtitledesk.vocabulary_ui.filedialog.asksaveasfilename', return_value=str(output)), \
                     patch('subtitledesk.vocabulary_ui.messagebox.showwarning'):
                    dialog.export()
                    self.wait(app, dialog)
                self.assertTrue(output.exists())
                self.assertFalse(english.exists())
                self.assertFalse(vietnamese.exists())
                self.assertTrue(changed.exists())
            finally:
                app.close()


if __name__ == '__main__':
    unittest.main()
