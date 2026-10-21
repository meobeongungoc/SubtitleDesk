import io
import os
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from subtitledesk.core import (
    MAX_SUBTITLE, Movie, decode_subtitle, match_score, parse_movie, save_subtitle, unpack_subtitles)
from subtitledesk.storage import SecretStore, load_settings, write_json
from subtitledesk.players import MpcBe

SRT = "1\n00:00:00,000 --> 00:00:02,000\nXin chào Việt Nam.\n".encode("utf-8")


def archive(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as file:
        for name, data in entries:
            file.writestr(name, data)
    return stream.getvalue()


class CoreTests(unittest.TestCase):
    def test_episode_and_release(self):
        movie = parse_movie(r"D:\Phim\Some.Show.S02E03.2024.1080p.WEB-DL-GROUP.mkv")
        self.assertEqual(movie, Movie("Some Show", "2024", "2", "3", "1080p WEB-DL-GROUP"))

    def test_alternative_episode(self):
        self.assertEqual(parse_movie("My.Show.3x07.720p.mkv").episode, "7")

    def test_vietnamese_and_number_title(self):
        self.assertEqual(parse_movie("Đào, phở và piano (2024).mkv").title, "Đào, phở và piano")
        self.assertEqual(parse_movie("1917.2019.1080p.mkv").title, "1917")

    def test_wrong_episode_scores_lower(self):
        movie = Movie("Some Show", season="2", episode="3")
        good = match_score(movie, "Some.Show.S02E03.1080p", "", "vi", ["vi", "en"])
        bad = match_score(movie, "Some.Show.S02E04.1080p", "", "vi", ["vi", "en"])
        self.assertGreater(good[0], bad[0])
        self.assertIn("Different episode", bad[1])

    def test_utf8_utf16(self):
        self.assertIn("Việt Nam", decode_subtitle(SRT))
        self.assertIn("Việt Nam", decode_subtitle(SRT.decode().encode("utf-16")))

    def test_invalid_subtitle(self):
        for data in (b"", b"not a subtitle", b"\0\0-->", b"x" * (MAX_SUBTITLE + 1)):
            with self.subTest(data=data[:10]), self.assertRaises(ValueError):
                decode_subtitle(data)

    def test_zip_ignores_executables(self):
        values = unpack_subtitles("movie.zip", archive([("en/movie.srt", SRT), ("run.exe", b"MZ")]))
        self.assertEqual(values, [("en/movie.srt", SRT)])

    def test_zip_traversal_and_drive(self):
        for name in ("../escape.srt", "/escape.srt", "C:/escape.srt", "..\\escape.srt"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                unpack_subtitles("bad.zip", archive([(name, SRT)]))

    def test_zip_symlink(self):
        link = zipfile.ZipInfo("link.srt")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaises(ValueError):
            unpack_subtitles("bad.zip", archive([(link, b"target")]))

    def test_zip_limits(self):
        with self.assertRaises(ValueError):
            unpack_subtitles("bad.zip", archive([(f"{i}.srt", SRT) for i in range(201)]))
        with self.assertRaises(ValueError):
            unpack_subtitles("bad.zip", archive([("bomb.srt", b"x" * (2 * 1024 * 1024))]))

    def test_unsupported_archive(self):
        with self.assertRaises(ValueError):
            unpack_subtitles("movie.rar", b"RAR")

    def test_save_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sub.srt"
            save_subtitle(path, SRT)
            with self.assertRaises(FileExistsError):
                save_subtitle(path, b"other")
            self.assertEqual(path.read_bytes(), SRT)
            save_subtitle(path, b"replacement", overwrite=True)
            self.assertEqual(path.read_bytes(), b"replacement")
            with self.assertRaises(ValueError):
                save_subtitle(Path(directory) / "movie.mkv", SRT)

    def test_hardlink_target_not_truncated(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "movie.mkv"
            original.write_bytes(b"important movie")
            link = Path(directory) / "sub.srt"
            os.link(original, link)
            save_subtitle(link, SRT, overwrite=True)
            self.assertEqual(original.read_bytes(), b"important movie")

    def test_settings_roundtrip_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = load_settings(root)
            value["languages"] = "en,vi"
            write_json(root / "settings.json", value)
            self.assertEqual(load_settings(root)["languages"], "en,vi")
            (root / "settings.json").write_text("{", "utf-8")
            with self.assertRaises(ValueError):
                load_settings(root)
            self.assertEqual((root / "settings.json").read_text(), "{")

    @unittest.skipUnless(os.name == "nt", "Windows DPAPI")
    def test_dpapi_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SecretStore(Path(directory))
            secret = "TEST-ONLY-không-phải-khóa-thật"
            store.set("fixture", "api_key", secret)
            self.assertEqual(store.get("fixture", "api_key"), secret)
            self.assertNotIn(secret, store.path.read_text("utf-8"))
            store.set("fixture", "api_key", "")
            self.assertEqual(store.get("fixture", "api_key"), "")

    def test_mpc_arguments_no_shell(self):
        command = MpcBe().command(Path(r"D:\Program\MPC-BE\mpc-be64.exe"),
                                  Path(r"D:\Movies\Phim & bạn.mkv"), Path(r"D:\Subs\Việt Nam.srt"))
        self.assertEqual(len(command), 4)
        self.assertEqual(command[2], "/sub")
        self.assertTrue(Path(command[3]).is_absolute())
