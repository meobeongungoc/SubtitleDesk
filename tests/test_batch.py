import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from subtitledesk.batch import Episode, identify, scan_folder, rank, select_file, save_episode
from subtitledesk.core import Movie
from subtitledesk.providers import Result
from test_core import SRT


class BatchTests(unittest.TestCase):
    def result(self, **values):
        return replace(Result("fixture", "1", "Show", "vi", "Show.S01E02.1080p",
                              season="1", episode="2"), **values)

    def test_identify_formats_and_parent(self):
        for name in ("Show.S01E02.mkv", "Show.1x02.mkv"):
            self.assertEqual((identify(Path(name)).season, identify(Path(name)).episode), ("1", "2"))
        movie = identify(Path("Season 2") / "Show.Tap.03.mp4")
        self.assertEqual((movie.title, movie.season, movie.episode), ("Show", "2", "3"))
        self.assertEqual(identify(Path("Show.E03.mkv"), "Corrected", "1").title, "Corrected")

    def test_multi_episode_requires_manual(self):
        for name in ("Show.S01E01E02.mkv", "Show.S01E01-E03.mkv", "Show.Tap.1-2.mkv"):
            self.assertEqual(identify(Path(name)).episode, "")

    def test_folder_skip_existing_and_order(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "Show.S01E02.mkv").write_bytes(b"video")
            (root / "Show.S01E01.mkv").write_bytes(b"video")
            (root / "Show.S01E01.vi.srt").write_bytes(SRT)
            rows = scan_folder(root)
            self.assertEqual([r.movie.episode for r in rows], ["1", "2"])
            self.assertFalse(rows[0].enabled)
            self.assertTrue(rows[1].enabled)

    def test_rank_rejects_wrong_episode_and_language(self):
        movie = Movie("Show", season="1", episode="2")
        self.assertGreaterEqual(rank(movie, self.result(), "vi"), 75)
        self.assertIsNone(rank(movie, self.result(episode="3"), "vi"))
        self.assertIsNone(rank(movie, self.result(language="en"), "vi"))
        self.assertIsNone(rank(movie, self.result(title="Unrelated", release="Other.S01E02"), "vi"))

    def test_pack_exact_selection_and_ambiguity(self):
        movie = Movie("Show", season="1", episode="2")
        pack = self.result(season_pack=True, episode="")
        files = [("Show.S01E01.srt", SRT), ("Show.S01E02.srt", SRT)]
        self.assertEqual(select_file(movie, pack, files)[0], "Show.S01E02.srt")
        with self.assertRaises(ValueError):
            select_file(movie, pack, files + [("alternate.S01E02.srt", SRT)])
        with self.assertRaises(ValueError):
            select_file(movie, pack, [("unknown.srt", SRT)])
        with self.assertRaises(ValueError):
            select_file(movie, self.result(), [("Show.S01E03.srt", SRT)])
        self.assertEqual(select_file(movie, self.result(season="01", episode="02"),
                                     [("subtitle.srt", SRT)])[1], SRT)

    def test_save_exact_stem_no_overwrite_video_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            video = Path(d) / "Show.S01E02.1080p.mkv"
            video.write_bytes(b"original-video")
            row = Episode(video, identify(video))
            saved = save_episode(row, "different.srt", SRT)
            self.assertEqual(saved, video.with_suffix(".srt"))
            self.assertIsNone(save_episode(row, "different.ass", SRT))
            self.assertEqual(saved.read_bytes(), SRT)
            self.assertEqual(video.read_bytes(), b"original-video")

    def test_missing_video_does_not_save(self):
        with tempfile.TemporaryDirectory() as d:
            video = Path(d) / "Show.S01E02.mkv"
            with self.assertRaises(ValueError):
                save_episode(Episode(video, identify(video)), "sub.srt", SRT)
