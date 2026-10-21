"""Optional real-player test through MPC-BE's documented /slave WM_COPYDATA API.
Creates a silent synthetic AVI and SRT in project test-artifacts.
Only closes the player process started by this script.
"""
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from subtitledesk.players import MpcBe

ROOT = Path(__file__).resolve().parent.parent / "test-artifacts"
ROOT.mkdir(exist_ok=True)


def chunk(tag, data):
    return tag + struct.pack("<I", len(data)) + data + (b"\0" if len(data) % 2 else b"")


def make_avi():
    width, height, fps, frames = 160, 90, 5, 25
    frame = bytes([55, 40, 25]) * width * height
    avih = struct.pack("<14I", 1000000 // fps, len(frame) * fps, 0, 0x10,
                       frames, 0, 1, len(frame), width, height, 0, 0, 0, 0)
    strh = struct.pack("<4s4sIHHIIIIIIIIhhhh", b"vids", b"DIB ", 0, 0, 0, 0,
                       1, fps, 0, frames, len(frame), 0xFFFFFFFF, 0, 0, 0, width, height)
    strf = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0, len(frame), 0, 0, 0, 0)
    header = chunk(b"LIST", b"hdrl" + chunk(b"avih", avih)
                   + chunk(b"LIST", b"strl" + chunk(b"strh", strh) + chunk(b"strf", strf)))
    movies, index = bytearray(), bytearray()
    for _ in range(frames):
        index.extend(struct.pack("<4sIII", b"00db", 0x10, 4 + len(movies), len(frame)))
        movies.extend(chunk(b"00db", frame))
    path = ROOT / "sample-video.avi"
    path.write_bytes(chunk(b"RIFF", b"AVI " + header + chunk(b"LIST", b"movi" + movies) + chunk(b"idx1", index)))
    subtitle = ROOT / "explicit-external-subtitle.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:05,000\nSubtitleDesk integration test\n", encoding="utf-8")
    return path, subtitle


def main():
    user = C.WinDLL("user32", use_last_error=True)
    kernel = C.WinDLL("kernel32", use_last_error=True)
    PROC = C.WINFUNCTYPE(C.c_ssize_t, W.HWND, W.UINT, W.WPARAM, W.LPARAM)

    class WNDCLASS(C.Structure):
        _fields_ = [("style", W.UINT), ("proc", PROC), ("clsExtra", C.c_int),
                    ("wndExtra", C.c_int), ("instance", W.HINSTANCE), ("icon", W.HICON),
                    ("cursor", W.HANDLE), ("background", W.HBRUSH),
                    ("menu", W.LPCWSTR), ("className", W.LPCWSTR)]

    class COPYDATA(C.Structure):
        _fields_ = [("data", C.c_size_t), ("size", W.DWORD), ("pointer", C.c_void_p)]

    user.DefWindowProcW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
    user.DefWindowProcW.restype = C.c_ssize_t
    user.CreateWindowExW.argtypes = [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD, C.c_int, C.c_int,
                                    C.c_int, C.c_int, W.HWND, W.HMENU, W.HINSTANCE, C.c_void_p]
    user.CreateWindowExW.restype = W.HWND
    kernel.GetModuleHandleW.argtypes = [W.LPCWSTR]
    kernel.GetModuleHandleW.restype = W.HMODULE
    user.RegisterClassW.argtypes = [C.POINTER(WNDCLASS)]
    user.RegisterClassW.restype = W.ATOM
    user.PeekMessageW.argtypes = [C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT, W.UINT]
    user.TranslateMessage.argtypes = [C.POINTER(W.MSG)]
    user.DispatchMessageW.argtypes = [C.POINTER(W.MSG)]
    user.DispatchMessageW.restype = C.c_ssize_t
    user.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
    user.SendMessageTimeoutW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM,
                                         W.UINT, W.UINT, C.POINTER(C.c_size_t)]
    user.SendMessageTimeoutW.restype = C.c_ssize_t
    user.DestroyWindow.argtypes = [W.HWND]
    user.UnregisterClassW.argtypes = [W.LPCWSTR, W.HINSTANCE]
    events = []
    player_hwnd = [None]

    @PROC
    def callback(hwnd, message, wparam, lparam):
        if message == 0x4A:
            item = C.cast(lparam, C.POINTER(COPYDATA)).contents
            if item.size <= 65536 and item.pointer:
                text = C.wstring_at(item.pointer, max(0, item.size // 2 - 1))
                events.append((hex(item.data), text))
                if item.data == 0x50000000:
                    player_hwnd[0] = int(text)
            return 1
        return user.DefWindowProcW(hwnd, message, wparam, lparam)

    instance = kernel.GetModuleHandleW(None)
    classname = "SubtitleDeskTestHost"
    wc = WNDCLASS(0, callback, 0, 0, instance, None, None, None, None, classname)
    if not user.RegisterClassW(C.byref(wc)):
        raise C.WinError(C.get_last_error())
    hwnd = user.CreateWindowExW(0, classname, "", 0, 0, 0, 0, 0, None, None, instance, None)
    if not hwnd:
        raise C.WinError(C.get_last_error())
    movie, subtitle = make_avi()
    command = MpcBe().command(Path(r"D:\Program\MPC-BE\mpc-be64.exe"), movie, subtitle)
    command += ["/new", "/minimized", "/nofocus", "/slave", str(hwnd)]
    start = subprocess.STARTUPINFO()
    start.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    start.wShowWindow = 0
    process = subprocess.Popen(command, startupinfo=start)

    def send(code):
        if not player_hwnd[0]:
            return
        pid = W.DWORD()
        user.GetWindowThreadProcessId(player_hwnd[0], C.byref(pid))
        if pid.value != process.pid:
            raise RuntimeError("Player window does not belong to this test.")
        text = C.create_unicode_buffer("")
        value = COPYDATA(code, C.sizeof(text), C.cast(text, C.c_void_p))
        result = C.c_size_t()
        user.SendMessageTimeoutW(player_hwnd[0], 0x4A, hwnd, C.addressof(value), 2, 1000, C.byref(result))

    try:
        deadline = time.monotonic() + 20
        last_query = 0
        while time.monotonic() < deadline and process.poll() is None:
            msg = W.MSG()
            while user.PeekMessageW(C.byref(msg), None, 0, 0, 1):
                user.TranslateMessage(C.byref(msg))
                user.DispatchMessageW(C.byref(msg))
            if player_hwnd[0] and time.monotonic() - last_query > 0.5:
                send(0xA0003000)
                send(0xA0003002)
                last_query = time.monotonic()
            tracks = [text for code, text in events if code == "0x50000004" and text not in ("-1", "-2", "")]
            # Installed 1.9.1 reports basename here, unlike the header's full-path description.
            playing = [text for code, text in events if code == "0x50000003"
                       and len(text.split("|")) >= 5
                       and Path(text.split("|")[3]).name.lower() == movie.name.lower()]
            if tracks and playing:
                result = {"passed": True, "subtitle_tracks": tracks[-1], "movie": str(movie),
                          "method": "MPC-BE /slave API + absolute /sub", "events": events}
                break
            time.sleep(0.02)
        else:
            result = {"passed": False, "events": events, "error": "No loaded movie and subtitle confirmation within 20s"}
        (ROOT / "mpc-live-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
        print(json.dumps(result, ensure_ascii=True))
    finally:
        if process.poll() is None:
            send(0xA0004006)
            try:
                process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=4)
        user.DestroyWindow(hwnd)
        user.UnregisterClassW(classname, instance)
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
