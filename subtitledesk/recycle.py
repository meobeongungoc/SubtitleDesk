"""Move selected local movie and subtitle files to the Windows Recycle Bin."""
import ctypes
from platform import version
from pathlib import Path

from send2trash.win.modern import send2trash

from .core import SUB_EXTENSIONS, VIDEO_EXTENSIONS


def _validate_file(path: Path, library_root: Path, extensions: set[str]) -> Path:
    if not str(library_root).strip() or str(library_root) == ".":
        raise ValueError("Choose a movie folder before moving files to the Recycle Bin.")
    path = Path(path).absolute()
    root = Path(library_root).absolute()
    if not root.is_dir() or path == root or not path.is_relative_to(root):
        raise ValueError("The file is outside the selected movie folder.")
    if path.suffix.lower() not in extensions or not path.is_file():
        raise ValueError("The selected file is missing or has an unsupported format.")
    item = path
    while True:
        if item.is_symlink() or getattr(item, "is_junction", lambda: False)():
            raise ValueError("Files reached through links cannot be moved by this action.")
        if item == root:
            break
        item = item.parent
    if path.resolve() != path or root.resolve() != root:
        raise ValueError("Files reached through links cannot be moved by this action.")
    if ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(path.anchor)) != 3:
        raise ValueError("Only files on a local fixed drive can be moved to the Recycle Bin.")
    return path


def validate_video(path: Path, library_root: Path) -> Path:
    return _validate_file(path, library_root, VIDEO_EXTENSIONS)


def validate_subtitle(path: Path, library_root: Path) -> Path:
    return _validate_file(path, library_root, SUB_EXTENSIONS)


def recycle_video(path: Path, library_root: Path) -> None:
    if int(version().split(".", 1)[0]) < 8:
        raise OSError("This Windows version cannot guarantee Recycle Bin deletion.")
    send2trash(str(validate_video(path, library_root)))


def recycle_subtitle(path: Path, library_root: Path) -> None:
    if int(version().split(".", 1)[0]) < 8:
        raise OSError("This Windows version cannot guarantee Recycle Bin deletion.")
    send2trash(str(validate_subtitle(path, library_root)))
