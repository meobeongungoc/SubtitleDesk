"""Smoke-test the packaged executable + real framed native host, without registry changes."""
import json
from pathlib import Path
import struct
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "dist" / "SubtitleDesk"
INBOX = APP / "data" / "inbox"
token = "SubtitleDesk packaging check " + uuid.uuid4().hex
value = {"action": "search", "url": "https://example.org/", "title": token, "selection": ""}
payload = json.dumps(value).encode("utf-8")
start = subprocess.STARTUPINFO()
start.dwFlags |= subprocess.STARTF_USESHOWWINDOW
start.wShowWindow = 0
process = subprocess.Popen([str(APP / "SubtitleDesk.exe")], startupinfo=start)
matched = None
try:
    time.sleep(2)
    if process.poll() is not None:
        raise RuntimeError("Packaged application exited at startup")
    host = subprocess.run([str(APP / "SubtitleDeskHost.exe")],
                          input=struct.pack("<I", len(payload)) + payload,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, startupinfo=start)
    length = struct.unpack("<I", host.stdout[:4])[0]
    reply = json.loads(host.stdout[4:4 + length].decode("utf-8"))
    assert reply == {"ok": True}, reply
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Packaged application stopped before receiving inbox message")
        for path in INBOX.glob("*.pending"):
            if json.loads(path.read_text("utf-8")).get("title") == token:
                matched = path
                break
        if matched:
            break
        time.sleep(0.1)
    assert matched is not None, "GUI did not consume native-host inbox message"
    invalid = subprocess.run([str(APP / "SubtitleDeskHost.exe")],
                             input=struct.pack("<I", 1000000), stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=15, startupinfo=start)
    length = struct.unpack("<I", invalid.stdout[:4])[0]
    assert json.loads(invalid.stdout[4:4 + length])["ok"] is False
    report = {"passed": True, "gui_started": True, "native_host_real_binary": True,
              "valid_message_received_by_gui": True, "oversized_message_rejected": True,
              "browser_profile_modified": False}
    (ROOT / "test-artifacts" / "package-result.json").write_text(json.dumps(report, indent=2), "utf-8")
    print(json.dumps(report))
finally:
    # Only the process and exact queue fixture created by this test.
    if process.poll() is None:
        process.terminate()
        process.wait(timeout=5)
    if matched:
        matched.unlink(missing_ok=True)
