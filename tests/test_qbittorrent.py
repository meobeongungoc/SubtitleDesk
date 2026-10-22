import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from subtitledesk.qbittorrent import QbitClient, QbitError, DownloadShutdown, content_file


class Handler(BaseHTTPRequestHandler):
    calls = []
    def log_message(self, *args):
        pass
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        self.calls.append((self.path, parse_qs(body)))
        if self.path.endswith("auth/login"):
            self.send_response(200)
            self.send_header("Set-Cookie", "SID=fixture; Path=/")
            self.end_headers()
            self.wfile.write(b"Ok.")
        elif self.path.endswith("search/start"):
            self.reply({"id": 7})
        else:
            self.reply("Ok.")
    def reply(self, value):
        self.send_response(200)
        self.end_headers()
        self.wfile.write((value if isinstance(value, str) else json.dumps(value)).encode())
    def do_GET(self):
        if self.headers.get("Cookie") != "SID=fixture":
            self.send_error(403)
            return
        parsed = urlparse(self.path)
        self.calls.append((parsed.path, parse_qs(parsed.query)))
        if parsed.path.endswith("app/version"):
            self.reply("v5.fixture")
        elif parsed.path.endswith("search/results"):
            self.reply({"status": "Stopped", "total": 1, "results": [
                {"fileName": "Ubuntu fixture", "fileUrl": "magnet:?xt=urn:btih:fixture",
                 "nbSeeders": 11, "nbLeechers": 3, "fileSize": 123}]})
        elif parsed.path.endswith("redirect"):
            self.send_response(302)
            self.send_header("Location", "https://example.org/")
            self.end_headers()
        else:
            self.reply([])


class QbitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def client(self):
        client = QbitClient(f"http://127.0.0.1:{self.server.server_port}", "user", "fixture")
        self.assertEqual(client.connect(), "v5.fixture")
        return client

    def test_login_cookie_and_list(self):
        self.assertEqual(self.client().torrents(), [])

    def test_graceful_shutdown_endpoint(self):
        self.client().shutdown()
        self.assertEqual(Handler.calls[-1], ("/api/v2/app/shutdown", {}))

    def test_download_shutdown_waits_for_real_completion_and_idle_work(self):
        monitor = DownloadShutdown()
        finished = [{"progress": 1.0, "state": "uploading"}]
        downloading = [{"progress": .8, "state": "downloading"}]
        self.assertFalse(monitor.update([{"progress": 1.0, "state": "checkingUP"}]))
        self.assertFalse(monitor.update(finished))
        self.assertFalse(monitor.update(downloading))
        self.assertFalse(monitor.update(finished, busy=True))
        self.assertFalse(monitor.update(finished))
        self.assertTrue(monitor.update(finished))
        self.assertFalse(monitor.update(finished))
        monitor.added()
        self.assertFalse(monitor.update([]))
        self.assertFalse(monitor.update([{"progress": 1.0, "state": "checkingUP"}]))
        self.assertFalse(monitor.update(finished))
        self.assertTrue(monitor.update(finished))

    def test_search_seeds_peers_and_cleanup(self):
        client = self.client()
        output = []
        status = client.search("Ubuntu", "enabled", threading.Event(), output.append)
        self.assertIn("complete", status)
        self.assertEqual((output[0]["nbSeeders"], output[0]["nbLeechers"]), (11, 3))
        self.assertEqual(Handler.calls[-1], ("/api/v2/search/delete", {"id": ["7"]}))

    def test_cancel_stops_own_job(self):
        client = self.client()
        cancel = threading.Event()
        cancel.set()
        self.assertIn("Cancelled", client.search("Ubuntu", "enabled", cancel, lambda r: self.fail()))
        self.assertEqual(Handler.calls[-2], ("/api/v2/search/stop", {"id": ["7"]}))

    def test_add_one_and_reject_multiple(self):
        client = self.client()
        client.add_url("magnet:?xt=urn:btih:fixture", "D:/Example")
        self.assertEqual(Handler.calls[-1][1]["savepath"], ["D:/Example"])
        with self.assertRaises(QbitError):
            client.add_url("magnet:?a\nmagnet:?b")
        with self.assertRaises(QbitError):
            client.add_url("file:///D:/file")

    def test_local_only_and_no_redirect(self):
        for url in ("http://192.168.1.2:8080", "http://user:pass@localhost:8080", "http://localhost/path"):
            with self.assertRaises(QbitError):
                QbitClient(url)
        with self.assertRaises(QbitError):
            self.client().request("redirect")

    def test_content_path_safety(self):
        with tempfile.TemporaryDirectory() as d:
            torrent = {"save_path": d}
            self.assertEqual(content_file(torrent, {"name": "Show/Show.S01E02.mkv"}),
                             (Path(d) / "Show/Show.S01E02.mkv").resolve())
            for name in ("../escape.mkv", "D:/escape.mkv", "/escape.mkv", "Show/x.mkv:ads"):
                with self.assertRaises(QbitError):
                    content_file(torrent, {"name": name})
