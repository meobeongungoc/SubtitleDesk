import threading
import time
import unittest
from dataclasses import replace

from subtitledesk.core import Movie
from subtitledesk.providers import (Capabilities, Cancelled, Context, Page, Query, Registry,
                                   Result, SearchEngine, load_registry, validate_url)


class FixtureProvider:
    def __init__(self, key, delay=0.01, error=False, timeout=1, paginate=False):
        self.capabilities = Capabilities(key, key, timeout=timeout, min_interval=0,
                                         pagination=paginate)
        self.delay = delay
        self.error = error
        self.calls = 0

    def search(self, query, cursor, context):
        self.calls += 1
        context.wait(self.delay)
        if self.error:
            raise RuntimeError("secret-must-not-leak")
        key = self.capabilities.id
        return Page([Result(key, "1", "Fixture Movie", "vi"), Result(key, "1", "Fixture Movie", "vi")],
                    "page2" if not cursor and self.capabilities.pagination else None)

    def download(self, result, context):
        context.check()
        return "fixture.srt", b"1\n00:00:00,000 --> 00:00:01,000\nFixture\n"


class ProviderTests(unittest.TestCase):
    def run_search(self, providers, cancel=None):
        registry = Registry()
        for provider in providers:
            registry.add(provider)
        engine = SearchEngine(registry)
        events = []
        engine.run(Query(Movie("Fixture Movie")), list(registry.providers),
                   cancel or threading.Event(), lambda *event: events.append(event))
        return events

    def test_production_registry_empty(self):
        self.assertEqual(load_registry().providers, {})

    def test_concurrency_isolation_and_dedup(self):
        events = self.run_search([FixtureProvider("good"), FixtureProvider("bad", error=True)])
        self.assertEqual(sum(e[0] == "result" for e in events), 1)
        self.assertTrue(any(e[0] == "error" and e[1] == "bad" for e in events))
        self.assertNotIn("secret-must-not-leak", str(events))
        self.assertEqual(events[-1][0], "done")

    def test_deadline_outside_uncooperative_provider(self):
        provider = FixtureProvider("slow", timeout=0.08)
        provider.search = lambda *args: (time.sleep(0.5) or Page())
        start = time.monotonic()
        events = self.run_search([provider])
        self.assertLess(time.monotonic() - start, 0.4)
        self.assertIn(("error", "slow", "TimeoutError"), events)

    def test_cancel(self):
        cancel = threading.Event()
        timer = threading.Timer(0.05, cancel.set)
        timer.start()
        events = self.run_search([FixtureProvider("slow", delay=1)], cancel)
        self.assertEqual(events[-1], ("done", "", "cancelled"))
        timer.join()

    def test_pagination(self):
        provider = FixtureProvider("pages", paginate=True)
        events = self.run_search([provider])
        self.assertEqual(provider.calls, 2)
        self.assertEqual(sum(e[0] == "result" for e in events), 1)

    def test_context_and_domain_checks(self):
        context = Context(threading.Event(), time.monotonic() - 1)
        with self.assertRaises(TimeoutError):
            context.check()
        for url in ("http://example.org/sub", "https://evil.org/sub",
                    "https://user:password@example.org/sub", "https://example.org:444/sub"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url, ("example.org",))
        validate_url("https://example.org/sub", ("example.org",))

    def test_download_rate_limit_and_deadline(self):
        provider = FixtureProvider("download")
        provider.capabilities = replace(provider.capabilities, min_interval=0.15)
        registry = Registry()
        registry.add(provider)
        engine = SearchEngine(registry)
        engine.last_calls["download"] = time.monotonic()
        start = time.monotonic()
        name, content = engine.download(Result("download", "1", "Fixture Movie", "vi"),
                                        Context(threading.Event(), start + 1))
        self.assertGreaterEqual(time.monotonic() - start, 0.13)
        self.assertEqual(name, "fixture.srt")
        self.assertIn(b"-->", content)
        with self.assertRaises(TimeoutError):
            engine.download(Result("download", "1", "Fixture Movie", "vi"),
                            Context(threading.Event(), time.monotonic() + 0.01))
