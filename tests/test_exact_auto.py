import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from subtitledesk.gui import Application
from subtitledesk.batch import scan_folder, exact_filename, rank
from subtitledesk.providers import Capabilities, Registry, SearchEngine, Result, Page
from subtitledesk.languages import LANGUAGES
from subtitledesk.core import Movie
from test_core import SRT


class Source:
    capabilities = Capabilities('subdl', 'Fixture SubDL', min_interval=0)
    downloads = 0
    def search(self, query, cursor, context):
        episode = query.movie.episode
        return Page([Result('subdl', episode, 'Show', 'vi', f'Show.S01E{int(episode):02d}',
                    season='1', episode=episode,
                    filename=f'Show.S01E{int(episode):02d}' + ('.srt' if episode == '1' else '.WEB-DL.srt'))])
    def download(self, result, context):
        self.downloads += 1
        return result.filename, SRT


class ExactAutoTests(unittest.TestCase):
    def test_exact_filename_is_strict_and_rejects_metadata_conflict(self):
        result = Result('subdl', '1', 'Show', 'vi', 'Show.S01E01', season='1', episode='1', filename='show.s01e01.srt')
        self.assertTrue(exact_filename(Path('Show.S01E01.mkv'), result))
        from dataclasses import replace
        self.assertTrue(exact_filename(Path('Show.S01E01.mkv'), replace(result, filename='Show.S01E01')))
        self.assertFalse(exact_filename(Path('Show.S01E01.1080p.mkv'), result))
        bad = Result('subdl', '2', 'Show', 'vi', 'Show.S02E01', season='1', episode='1')
        self.assertIsNone(rank(Movie('Show', season='1', episode='1'), bad, 'vi'))
        self.assertEqual([v[0] for v in LANGUAGES[:3]], ['Vietnamese', 'English', 'Vietnamese + English'])

    def test_three_lists_exact_saves_without_prompt_fuzzy_waits(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for episode in (1, 2):
                (root / f'Show.S01E{episode:02d}.mkv').write_bytes(b'video fixture')
            app = Application(root)
            app.root.withdraw()
            try:
                source = Source()
                app.registry = Registry()
                app.registry.add(source)
                app.engine = SearchEngine(app.registry)
                app.enabled = {'subdl': tk.BooleanVar(master=app.root, value=True)}
                library = app.library
                library.set_rows(scan_folder(root))
                with patch('subtitledesk.library_ui.messagebox.askyesno') as confirmation:
                    library.search_batch()
                    deadline = time.monotonic() + 8
                    while time.monotonic() < deadline:
                        app.root.update()
                        if not library.batch_busy and (root / 'Show.S01E01.vi.srt').exists():
                            break
                        time.sleep(.01)
                    confirmation.assert_not_called()
                self.assertEqual(source.downloads, 1)
                self.assertEqual((root / 'Show.S01E01.vi.srt').read_bytes(), SRT)
                self.assertFalse((root / 'Show.S01E02.vi.srt').exists())
                self.assertEqual(library.rows[1].state, 'Choose a subtitle')
                self.assertIn('Auto-saved', library.notice.get())
                self.assertEqual(len(library.panes.panes()), 3)
                self.assertEqual(set(library.source_views), {'subdl', 'opensubtitles'})
                self.assertEqual(library.source_views['subdl'].item('0', 'tags'), ('saved',))
            finally:
                app.close()
