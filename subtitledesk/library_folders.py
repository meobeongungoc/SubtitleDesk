"""Discover movie folders without walking application data or filesystem links."""
import os
from pathlib import Path
import time
from .core import VIDEO_EXTENSIONS


def discover_library(folder, excluded=()):
    root = Path(folder).resolve()
    if not root.is_dir():
        raise ValueError('Library folder is unavailable.')
    excluded = {Path(p).resolve() for p in excluded}
    found = {}
    deadline = time.monotonic() + 15
    for count, (directory, dirs, files) in enumerate(os.walk(root, followlinks=False)):
        if count > 10000 or time.monotonic() > deadline:
            raise ValueError('Library scan limit reached. Choose a smaller library root.')
        here = Path(directory)
        dirs[:] = [name for name in dirs if not name.startswith('.')
                   and not (here/name).is_symlink()
                   and not getattr(here/name, 'is_junction', lambda: False)()
                   and (here/name).resolve() not in excluded]
        if not any(Path(name).suffix.lower() in VIDEO_EXTENSIONS and not (here/name).is_symlink()
                   for name in files):
            continue
        relative = here.relative_to(root)
        if not relative.parts:
            found['Movies in library root'] = root
        else:
            # A series and its nested seasons form one selectable library item.
            name = relative.parts[0]
            found[name] = root/name
    return dict(sorted(found.items(), key=lambda pair: pair[0].casefold()))
