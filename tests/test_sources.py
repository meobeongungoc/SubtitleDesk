import threading
import time
import unittest
from unittest.mock import Mock, patch
from subtitledesk.core import Movie
from subtitledesk.providers import Query, Context, Result
from subtitledesk.sources import SubDL, OpenSubtitles, SourceError, error_text


class Secrets:
    def __init__(self, values=None):
        self.values = values or {}
    def get(self, source, field):
        return self.values.get(field, "")


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.ctx = Context(threading.Event(), time.monotonic() + 10)
        self.query = Query(Movie("Show", season="1", episode="2"), ("vi",))

    def test_missing_key_safe_error(self):
        for cls in (SubDL, OpenSubtitles):
            with self.assertRaisesRegex(SourceError, "Missing api_key"):
                cls(Secrets()).search(self.query, None, self.ctx)
        self.assertEqual(error_text(ValueError("secret-token")), "ValueError")

    def test_subdl_schema_and_pack(self):
        source = SubDL(Secrets({"api_key": "fixture-key"}))
        source.request = Mock(return_value={"status": True, "results": [{"name": "Show"}],
             "subtitles": [{"url": "/subtitle/123.zip", "lang": "Vietnamese", "release_name": "Show.S01",
                            "season": 1, "full_season": True, "author": "fixture"}]})
        result = source.search(self.query, None, self.ctx).results[0]
        self.assertTrue(result.season_pack)
        self.assertEqual(result.language, "vi")
        self.assertEqual(result.download_ref, "https://dl.subdl.com/subtitle/123.zip")
        self.assertIn("episode_number=2", source.request.call_args.args[0])

    def test_subdl_refuses_foreign_download(self):
        source = SubDL(Secrets({"api_key": "fixture"}))
        source.request = Mock(return_value={"subtitles": [{"url": "https://evil.invalid/file.zip"}]})
        with self.assertRaises(ValueError):
            source.search(self.query, None, self.ctx)

    def test_opensubtitles_schema_pagination(self):
        source = OpenSubtitles(Secrets({"api_key": "fixture"}))
        source.request = Mock(return_value={"page": 1, "total_pages": 2, "data": [{"attributes": {
            "language": "vi", "release": "Show.S01E02", "files": [{"file_id": 123}],
            "feature_details": {"parent_title": "Show", "season_number": 1, "episode_number": 2},
            "uploader": {"name": "fixture"}}}]})
        page = source.search(self.query, None, self.ctx)
        self.assertEqual(page.next_cursor, "2")
        self.assertEqual((page.results[0].season, page.results[0].episode), ("1", "2"))
        self.assertEqual(page.results[0].id, "123")

    def test_opensubtitles_download_credentials_not_forwarded(self):
        source = OpenSubtitles(Secrets({"api_key": "fixture", "username": "user", "password": "password"}))
        source.request = Mock(side_effect=[{"token": "token", "base_url": "vip-api.opensubtitles.com"},
                                           {"link": "https://dl.opensubtitles.com/example", "file_name": "sub.srt"}])
        with patch("subtitledesk.sources.fetch_bytes", return_value=b"fixture") as fetch:
            self.assertEqual(source.download(Result("opensubtitles", "123", "Show", "vi"), self.ctx),
                             ("sub.srt", b"fixture"))
            self.assertEqual(len(fetch.call_args.args), 3)
        self.assertEqual(source.request.call_args.args[2]["Authorization"], "Bearer token")

    def test_opensubtitles_rejects_foreign_login_host(self):
        source = OpenSubtitles(Secrets({"api_key": "fixture", "username": "user", "password": "password"}))
        source.request = Mock(return_value={"token": "token", "base_url": "evil.invalid"})
        with self.assertRaises(SourceError):
            source.download(Result("opensubtitles", "123", "Show", "vi"), self.ctx)
