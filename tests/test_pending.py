import hashlib
import tempfile
import time
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import Mock, patch
from subtitledesk.gui import Application
from subtitledesk.core import Movie
from subtitledesk.providers import Result
from subtitledesk.storage import write_json
from test_core import SRT


class PendingTests(unittest.TestCase):
    def test_restore_downloaded_subtitle_applies_without_redownloading(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            video = root / 'Show.S01E01.mkv'
            video.write_bytes(b'video fixture')
            data = root / 'data'
            cache = data / 'pending'
            cache.mkdir(parents=True)
            name = hashlib.sha256(SRT).hexdigest() + '.srt'
            (cache / name).write_bytes(SRT)
            result = Result('opensubtitles', 'fixture', 'Show', 'vi', 'Show.S01E01',
                            season='1', episode='1', filename='Show.S01E01.srt')
            write_json(data / 'pending-subtitles.json', [{'path':str(video), 'movie':asdict(Movie('Show',season='1',episode='1')),
                'selected':asdict(result), 'cached_subtitle':name, 'torrent_hash':'fixture', 'file_index':0,
                'progress':.5, 'automatic':True}])
            app = Application(root)
            app.root.withdraw()
            try:
                library = app.library
                library.restore_pending()
                self.assertEqual(library.queued, {0})
                self.assertIn('Auto-downloaded', library.notice.get())
                library.client = Mock()
                library.client.torrents.return_value = [{'hash':'fixture','save_path':str(root)}]
                library.client.files.return_value = [{'index':0,'name':video.name,'progress':1,'priority':1}]
                library.connected = True
                library.last_refresh = time.monotonic()
                with patch.object(app.engine, 'download', side_effect=AssertionError('Must not download again')):
                    library.download_batch(automatic=True)
                    deadline = time.monotonic()+5
                    while library.batch_busy and time.monotonic()<deadline:
                        app.root.update()
                        time.sleep(.01)
                self.assertEqual(video.with_suffix('.srt').read_bytes(),SRT)
                self.assertEqual(library.queued,set())
                self.assertIn('Auto-saved',library.notice.get())
            finally:
                app.close()
