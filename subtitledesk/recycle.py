"""Move selected local-library videos to the Windows Recycle Bin."""
import ctypes
from platform import version
from pathlib import Path

from send2trash.win.modern import send2trash

from .core import VIDEO_EXTENSIONS


def validate_video(path: Path, library_root: Path) -> Path:
    if not str(library_root).strip() or str(library_root) == ".":
        raise ValueError("Choose a movie library before moving videos to the Recycle Bin.")
    path = Path(path).absolute()
    root = Path(library_root).absolute()
    if not root.is_dir() or path == root or not path.is_relative_to(root):
        raise ValueError("The video is outside the selected movie library.")
    if path.suffix.lower() not in VIDEO_EXTENSIONS or not path.is_file():
        raise ValueError("The selected video is missing or has an unsupported format.")
    item = path
    while True:
        if item.is_symlink() or getattr(item, "is_junction", lambda: False)():
            raise ValueError("Videos reached through links cannot be moved by this action.")
        if item == root:
            break
        item = item.parent
    if path.resolve() != path or root.resolve() != root:
        raise ValueError("Videos reached through links cannot be moved by this action.")
    if ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(path.anchor)) != 3:
        raise ValueError("Only videos on a local fixed drive can be moved to the Recycle Bin.")
    return path


def recycle_video(path: Path, library_root: Path) -> None:
    if int(version().split(".", 1)[0]) < 8:
        raise OSError("This Windows version cannot guarantee Recycle Bin deletion.")
    send2trash(str(validate_video(path, library_root)))
