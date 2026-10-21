import ctypes
import hashlib
import os
from subtitledesk.bridge import app_root


def main():
    root = app_root()
    mutex = None
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel.CreateMutexW.restype = ctypes.c_void_p
        name = "Local\\SubtitleDesk_" + hashlib.sha256(str(root).lower().encode()).hexdigest()[:20]
        mutex = kernel.CreateMutexW(None, False, name)
        if not mutex:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == 183:
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle(mutex)
            return
    from subtitledesk.gui import Application
    try:
        Application(root).run()
    finally:
        if mutex:
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle(mutex)


if __name__ == "__main__":
    main()
