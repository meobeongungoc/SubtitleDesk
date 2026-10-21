"""Local qBittorrent WebUI client. No GUI automation and no destructive endpoints."""
from __future__ import annotations
import http.cookiejar
import json
import subprocess
import threading
import time
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urlencode, urlparse
import urllib.error
import urllib.request


class QbitError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise QbitError("Unexpected API redirect; check the qBittorrent address.")


class QbitClient:
    def __init__(self, url, username="", password="", executable=""):
        parsed = urlparse(url)
        if (parsed.scheme not in ("http", "https") or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
                or parsed.username or parsed.password or parsed.path not in ("", "/")
                or parsed.query or parsed.fragment):
            raise QbitError("Connect to qBittorrent on this machine using localhost/127.0.0.1.")
        self.url = url.rstrip("/")
        self.username, self.password, self.executable = username, password, executable
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.lock = threading.Lock()

    def request(self, endpoint, parameters=None, post=False, raw=False, body=None, content_type=None):
        url = self.url + "/api/v2/" + endpoint
        data = None
        headers = {"Referer": self.url, "Origin": self.url}
        if post:
            data = body if body is not None else urlencode(parameters or {}).encode()
            headers["Content-Type"] = content_type or "application/x-www-form-urlencoded"
        elif parameters:
            url += "?" + urlencode(parameters)
        request = urllib.request.Request(url, data=data, headers=headers)
        with self.lock:
            try:
                with self.opener.open(request, timeout=6) as response:
                    output = response.read(16 * 1024 * 1024 + 1)
            except urllib.error.HTTPError as exc:
                code = exc.code
                exc.close()
                if code == 403:
                    raise QbitError("qBittorrent requires authentication or has blocked login. Check the WebUI account.") from None
                raise QbitError(f"qBittorrent trả HTTP {code}; kiểm tra kết nối/plugin.") from None
            except (urllib.error.URLError, TimeoutError, OSError):
                raise QbitError("Cannot connect to qBittorrent. Check its WebUI, port and application status.") from None
        if len(output) > 16 * 1024 * 1024:
            raise QbitError("qBittorrent response exceeded the size limit.")
        text = output.decode("utf-8")
        if raw:
            return text
        try:
            return json.loads(text) if text else None
        except ValueError:
            raise QbitError("Invalid JSON response from qBittorrent.") from None

    def connect(self, launch=False):
        # A TCP probe distinguishes a stopped server from authentication errors.
        import socket
        parsed = urlparse(self.url)
        available = False
        try:
            with socket.create_connection((parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)), timeout=1):
                available = True
        except OSError:
            pass
        if not available and launch:
            exe = Path(self.executable)
            if not exe.is_file() or exe.name.lower() != "qbittorrent.exe":
                raise QbitError("Choose the correct qbittorrent.exe in connection settings.")
            start = subprocess.STARTUPINFO() if hasattr(subprocess, "STARTUPINFO") else None
            if start:
                start.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                start.wShowWindow = 0
            subprocess.Popen([str(exe)], cwd=exe.parent, startupinfo=start)
            for _ in range(15):
                try:
                    with socket.create_connection((parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)), timeout=.5):
                        available = True
                        break
                except OSError:
                    time.sleep(.5)
        if not available:
            raise QbitError("qBittorrent is not running or its WebUI is disabled. See the connection guide.")
        if self.password:
            response = self.request("auth/login", {"username": self.username, "password": self.password},
                                    post=True, raw=True)
            if response.strip() != "Ok.":
                raise QbitError("WebUI login failed. Automatic retries are disabled to avoid account lockout.")
        return self.request("app/version", raw=True).strip()

    def torrents(self, torrent_hash=None):
        return self.request("torrents/info", {"hashes": torrent_hash} if torrent_hash else None)

    def files(self, torrent_hash):
        return self.request("torrents/files", {"hash": torrent_hash})

    def peers(self, torrent_hash):
        return self.request("sync/torrentPeers", {"hash": torrent_hash, "rid": 0})

    def plugins(self):
        return self.request("search/plugins")

    def set_default_save_path(self, folder):
        path = Path(folder).resolve()
        if not path.is_dir():
            raise QbitError('Library folder is unavailable.')
        self.request('app/setPreferences', {'json': json.dumps({'save_path': str(path)})},
                     post=True, raw=True)
        current = self.request('app/preferences')['save_path']
        if Path(current).resolve() != path:
            raise QbitError('qBittorrent did not keep the requested library folder.')

    def add_url(self, url, save_path=""):
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("magnet", "https", "http"):
            raise QbitError("Use a magnet link or an HTTP/HTTPS torrent URL.")
        if "\n" in url or "\r" in url:
            raise QbitError("Add one torrent at a time.")
        parameters = {"urls": url.strip()}
        if save_path:
            parameters["savepath"] = save_path
        response = self.request("torrents/add", parameters, post=True, raw=True)
        if response.strip() != "Ok.":
            raise QbitError("qBittorrent did not accept this torrent.")

    def add_file(self, filename, save_path=""):
        import uuid
        path = Path(filename)
        if path.suffix.lower() != ".torrent":
            raise QbitError("Chọn file .torrent.")
        with path.open("rb") as stream:
            content = stream.read(10 * 1024 * 1024 + 1)
        if len(content) > 10 * 1024 * 1024:
            raise QbitError("Torrent file exceeds 10 MB.")
        boundary = "SubtitleDesk" + uuid.uuid4().hex
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="torrents"; filename="selected.torrent"\r\n'
                'Content-Type: application/x-bittorrent\r\n\r\n').encode() + content + b"\r\n"
        if save_path:
            body += (f'--{boundary}\r\nContent-Disposition: form-data; name="savepath"\r\n\r\n{save_path}\r\n').encode()
        body += f"--{boundary}--\r\n".encode()
        if self.request("torrents/add", post=True, raw=True, body=body,
                        content_type=f"multipart/form-data; boundary={boundary}").strip() != "Ok.":
            raise QbitError("qBittorrent did not accept the torrent file.")

    def search(self, pattern, plugin, cancel, emit):
        job = self.request("search/start", {"pattern": pattern, "plugins": plugin, "category": "all"}, post=True)["id"]
        offset = 0
        deadline = time.monotonic() + 120
        try:
            while not cancel.is_set() and time.monotonic() < deadline:
                page = self.request("search/results", {"id": job, "offset": offset, "limit": 100})
                results = page.get("results") or []
                for result in results:
                    emit(result)
                offset += len(results)
                if page.get("status") != "Running" and offset >= page.get("total", offset):
                    return "Search complete."
                if offset >= 3000:
                    return "3,000 results received; narrow your search."
                if not results:
                    cancel.wait(1)
            return "Cancelled or search timed out (120 seconds)."
        finally:
            try:
                self.request("search/stop", {"id": job}, post=True, raw=True)
                self.request("search/delete", {"id": job}, post=True, raw=True)
            except QbitError:
                pass


def content_file(torrent, file):
    """Resolve relative API file names under save_path, never traverse outside."""
    name = str(file["name"]).replace("\\", "/")
    relative = PurePosixPath(name)
    if relative.is_absolute() or PureWindowsPath(name).drive or ".." in relative.parts or ":" in name:
        raise QbitError("qBittorrent returned an unsafe file path.")
    base = Path(torrent["save_path"]).resolve()
    path = (base / name).resolve()
    if not path.is_relative_to(base):
        raise QbitError("The file is outside the torrent save directory.")
    return path
