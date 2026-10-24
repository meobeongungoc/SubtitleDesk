"""Opt-in Windows background launch without activating the user's window."""
import ctypes
from ctypes import wintypes
import os


def prepare_background_start(root):
    if os.name != "nt" or os.environ.get("SUBTITLEDESK_BACKGROUND_START") != "1":
        return lambda: None
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.GetParent.argtypes = [wintypes.HWND]
    user.GetParent.restype = wintypes.HWND
    get_style = user.GetWindowLongPtrW
    get_style.argtypes = [wintypes.HWND, ctypes.c_int]
    get_style.restype = ctypes.c_ssize_t
    set_style = user.SetWindowLongPtrW
    set_style.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    set_style.restype = ctypes.c_ssize_t
    user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user.SetWindowPos.restype = wintypes.BOOL
    hwnd = user.GetParent(root.winfo_id())
    no_activate = 0x08000000
    set_style(hwnd, -20, get_style(hwnd, -20) | no_activate)

    def finish():
        # Tk can replace its native wrapper while configuring the initial window.
        current = user.GetParent(root.winfo_id())
        set_style(current, -20, get_style(current, -20) | no_activate)
        # Reveal a window launched with STARTUPINFO.wShowWindow=0 at HWND_BOTTOM.
        # NOSIZE | NOMOVE | NOACTIVATE | SHOWWINDOW; later user clicks work normally.
        user.SetWindowPos(current, 1, 0, 0, 0, 0, 0x0053)
        root.after(100, lambda: set_style(current, -20, get_style(current, -20) & ~no_activate))
    return finish
