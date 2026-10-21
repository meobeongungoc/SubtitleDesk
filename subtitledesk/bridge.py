import json
import os
import struct
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

MAX_MESSAGE = 64 * 1024


def app_root() -> Path:
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent


def validate_message(value) -> dict:
    if not isinstance(value, dict) or value.get("action") != "search":
        raise ValueError("Yêu cầu không hợp lệ.")
    clean = {"action": "search"}
    for key, limit in (("url", 8192), ("title", 1024), ("selection", 2048)):
        item = value.get(key, "")
        if not isinstance(item, str) or len(item) > limit or "\x00" in item:
            raise ValueError("Thông tin trình duyệt không hợp lệ.")
        clean[key] = item
    parsed = urlparse(clean["url"])
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username or parsed.password):
        raise ValueError("Chỉ nhận địa chỉ trang HTTP/HTTPS.")
    return clean


def read_exact(stream, size):
    output = bytearray()
    while len(output) < size:
        chunk = stream.read(size - len(output))
        if not chunk:
            raise ValueError("Thông điệp bị cắt.")
        output.extend(chunk)
    return bytes(output)


def read_message(stream) -> dict:
    size = struct.unpack("<I", read_exact(stream, 4))[0]
    if not 0 < size <= MAX_MESSAGE:
        raise ValueError("Thông điệp quá lớn.")
    return validate_message(json.loads(read_exact(stream, size).decode("utf-8")))


def write_message(stream, message):
    payload = json.dumps(message, ensure_ascii=False).encode("utf-8")
    stream.write(struct.pack("<I", len(payload)) + payload)
    stream.flush()


def enqueue(root: Path, message: dict):
    message = validate_message(message)
    inbox = root / "data" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    if len(list(inbox.glob("*.json"))) >= 30:
        raise ValueError("Hàng đợi đầy; hãy mở SubtitleDesk xử lý các yêu cầu trước.")
    path = inbox / f"{uuid.uuid4().hex}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(message, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)
    return path


def native_main():
    if os.name == "nt":
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    path = None
    try:
        value = read_message(sys.stdin.buffer)
        root = app_root()
        path = enqueue(root, value)
        if getattr(sys, "frozen", False):
            command = [str(root / "SubtitleDesk.exe")]
        else:
            command = [str(Path(sys.executable).with_name("pythonw.exe")), str(root / "main.py")]
        subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True)
        write_message(sys.stdout.buffer, {"ok": True})
    except Exception:
        if path is not None:
            path.unlink(missing_ok=True)
        write_message(sys.stdout.buffer, {"ok": False, "error": "Không gửi được. Mở SubtitleDesk và kiểm tra kết nối."})
