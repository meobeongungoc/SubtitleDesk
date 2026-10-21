import io
import json
import struct
import tempfile
import unittest
from pathlib import Path
from subtitledesk.bridge import enqueue, read_message, validate_message, write_message


MESSAGE = {"action": "search", "url": "https://example.org/movie", "title": "Phim Việt", "selection": ""}


class BridgeTests(unittest.TestCase):
    def test_framing_unicode_roundtrip(self):
        stream = io.BytesIO()
        write_message(stream, MESSAGE)
        stream.seek(0)
        self.assertEqual(read_message(stream), MESSAGE)

    def test_invalid_input(self):
        messages = [
            {**MESSAGE, "action": "execute"}, {**MESSAGE, "url": "file:///D:/program.exe"},
            {**MESSAGE, "title": "x" * 1025}, {**MESSAGE, "selection": ["bad"]},
            {**MESSAGE, "url": "https://user:password@example.org/"},
        ]
        for value in messages:
            with self.subTest(value=str(value)[:80]), self.assertRaises(ValueError):
                validate_message(value)
        with self.assertRaises(ValueError):
            read_message(io.BytesIO(struct.pack("<I", 1000000)))
        with self.assertRaises(ValueError):
            read_message(io.BytesIO(struct.pack("<I", 10) + b"{}"))

    def test_inbox_only_validated_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = enqueue(Path(directory), {**MESSAGE, "command": "malicious ignored field"})
            self.assertEqual(json.loads(path.read_text("utf-8")), MESSAGE)
            self.assertFalse(list(path.parent.glob("*.tmp")))
            for index in range(29):
                enqueue(Path(directory), MESSAGE)
            with self.assertRaises(ValueError):
                enqueue(Path(directory), MESSAGE)
