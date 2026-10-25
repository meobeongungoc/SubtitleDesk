import tempfile
import unittest
from pathlib import Path
from subtitledesk.library_folders import discover_library
from subtitledesk.gui import Application


class LibraryTests(unittest.TestCase):
    def test_series_nested_seasons_and_app_exclusion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('Show/Season 1/S01E01.mkv', 'Show/Season 2/S02E01.mp4',
                         'Movie/Movie.mkv', 'Tool/tests/fixture.mkv', 'Loose.mkv'):
                path = root/name
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(b'fixture')
            (root/'Empty').mkdir()
            catalog=discover_library(root,[root/'Tool'])
            self.assertEqual(set(catalog), {'Show','Movie','Movies in library root'})
            self.assertEqual(catalog['Show'], (root/'Show').resolve())

    def test_switch_blocked_during_subtitle_work(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Application(Path(directory))
            app.root.withdraw()
            try:
                lib=app.library
                app.settings['library_selection']='Current show'
                lib.movie_choice.set('Another show')
                lib.batch_busy = True
                lib.select_library_movie()
                self.assertEqual(lib.movie_choice.get(),'Current show')
                self.assertTrue(lib.batch_busy)
                lib.batch_busy = False
            finally:
                app.close()
