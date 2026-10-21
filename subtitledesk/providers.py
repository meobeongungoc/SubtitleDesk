from __future__ import annotations

import queue
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlparse

from .core import MAX_ARCHIVE, Movie


@dataclass(frozen=True)
class Capabilities:
    id: str
    name: str
    languages: tuple[str, ...] = ("vi", "en")
    search: bool = True
    download: bool = True
    pagination: bool = False
    credentials: tuple[str, ...] = ()
    min_interval: float = 1.0
    timeout: float = 15.0
    domains: tuple[str, ...] = ()


@dataclass(frozen=True)
class Query:
    movie: Movie
    languages: tuple[str, ...] = ("vi", "en")


@dataclass(frozen=True)
class Result:
    provider: str
    id: str
    title: str
    language: str
    release: str = ""
    uploader: str = ""
    quality: str = ""
    page_url: str = ""
    download_ref: str = ""
    season: str = ""
    episode: str = ""
    season_pack: bool = False
    filename: str = ""


@dataclass
class Page:
    results: list[Result] = field(default_factory=list)
    next_cursor: str | None = None


class Cancelled(Exception):
    pass


@dataclass
class Context:
    cancel: threading.Event
    deadline: float

    def check(self):
        if self.cancel.is_set():
            raise Cancelled("Cancelled.")
        if time.monotonic() >= self.deadline:
            raise TimeoutError("Provider response timed out.")

    def wait(self, seconds: float):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.check()
            self.cancel.wait(min(0.05, max(0, end - time.monotonic())))
        self.check()


class Provider(Protocol):
    capabilities: Capabilities

    def search(self, query: Query, cursor: str | None, context: Context) -> Page: ...

    def download(self, result: Result, context: Context) -> tuple[str, bytes]: ...


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, domains):
        self.domains = domains

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl, self.domains)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def validate_url(url: str, domains: tuple[str, ...]):
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or not parsed.hostname or parsed.hostname not in domains
            or parsed.port not in (None, 443)):
        raise ValueError("Download URL is outside the declared HTTPS provider domains.")


def fetch_bytes(url: str, domains: tuple[str, ...], context: Context,
                headers: dict[str, str] | None = None) -> bytes:
    """Provider-owned HTTPS transport. Never log URLs, headers or credentials."""
    validate_url(url, domains)
    context.check()
    opener = urllib.request.build_opener(SafeRedirect(domains))
    request = urllib.request.Request(url, headers=headers or {"User-Agent": "SubtitleDesk/0.1"})
    timeout = max(0.1, min(8, context.deadline - time.monotonic()))
    with opener.open(request, timeout=timeout) as response:
        validate_url(response.url, domains)
        output = bytearray()
        while True:
            context.check()
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            output.extend(chunk)
            if len(output) > MAX_ARCHIVE:
                raise ValueError("Download exceeds 32 MB.")
        return bytes(output)


class Registry:
    def __init__(self):
        self.providers: dict[str, Provider] = {}

    def add(self, provider: Provider):
        key = provider.capabilities.id
        if key in self.providers:
            raise ValueError(f"Duplicate provider ID: {key}")
        self.providers[key] = provider


class SearchEngine:
    """Bounded daemon workers; deadlines also enforced outside provider code."""
    def __init__(self, registry: Registry):
        self.registry = registry
        self.slots = threading.BoundedSemaphore(4)
        self.source_locks = {}
        self.last_calls = {}
        self.guard = threading.Lock()

    def download(self, result: Result, context: Context) -> tuple[str, bytes]:
        provider = self.registry.providers[result.provider]
        key = provider.capabilities.id
        lock = self.source_locks.setdefault(key, threading.Lock())
        acquired = False
        try:
            while not acquired:
                context.check()
                acquired = lock.acquire(timeout=0.05)
            context.wait(max(0, self.last_calls.get(key, 0)
                             + provider.capabilities.min_interval - time.monotonic()))
            self.last_calls[key] = time.monotonic()
            answer = provider.download(result, context)
            context.check()
            if len(answer[1]) > MAX_ARCHIVE:
                raise ValueError("Download exceeds the size limit.")
            return answer
        finally:
            if acquired:
                lock.release()

    def run(self, query: Query, ids: list[str], cancel: threading.Event,
            emit, max_pages: int = 3):
        work = queue.Queue()
        pending = {}
        seen = set()

        def worker(provider, context):
            key = provider.capabilities.id
            acquired = False
            lock = self.source_locks.setdefault(key, threading.Lock())
            locked = False
            try:
                while not acquired:
                    context.check()
                    acquired = self.slots.acquire(timeout=0.05)
                while not locked:
                    context.check()
                    locked = lock.acquire(timeout=0.05)
                cursor = None
                cursors = set()
                for _ in range(max_pages):
                    context.wait(max(0, self.last_calls.get(key, 0)
                                     + provider.capabilities.min_interval - time.monotonic()))
                    self.last_calls[key] = time.monotonic()
                    page = provider.search(query, cursor, context)
                    context.check()
                    for result in page.results[:500]:
                        if result.provider != key:
                            raise ValueError("Provider returned an invalid source ID.")
                        work.put(("result", key, result))
                    cursor = page.next_cursor
                    if not provider.capabilities.pagination or not cursor or cursor in cursors:
                        break
                    cursors.add(cursor)
                work.put(("source_done", key, None))
            except Cancelled:
                work.put(("source_cancelled", key, None))
            except Exception as exc:
                # Exception strings can contain credentials/URL query tokens.
                from .sources import error_text
                work.put(("error", key, error_text(exc)))
            finally:
                if locked:
                    lock.release()
                if acquired:
                    self.slots.release()

        for key in ids:
            provider = self.registry.providers[key]
            if not provider.capabilities.search:
                continue
            context = Context(cancel, time.monotonic() + provider.capabilities.timeout)
            pending[key] = context.deadline
            threading.Thread(target=worker, args=(provider, context), daemon=True).start()
        while pending and not cancel.is_set():
            now = time.monotonic()
            for key, deadline in list(pending.items()):
                if now >= deadline:
                    pending.pop(key)
                    emit("error", key, "TimeoutError")
            try:
                kind, key, value = work.get(timeout=0.04)
            except queue.Empty:
                continue
            if key not in pending:
                continue
            if kind == "result":
                identity = (value.provider, value.id)
                if identity not in seen:
                    seen.add(identity)
                    emit(kind, key, value)
            else:
                pending.pop(key, None)
                emit(kind, key, value)
        emit("done", "", "cancelled" if cancel.is_set() else "complete")


def load_registry(secret_store=None) -> Registry:
    # Explicit registrations only; never execute downloaded plugin files.
    registry = Registry()
    if secret_store is not None:
        from .sources import SubDL, OpenSubtitles
        registry.add(SubDL(secret_store))
        registry.add(OpenSubtitles(secret_store))
    return registry
