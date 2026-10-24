import subprocess
from pathlib import Path
from typing import Protocol

from .core import SUB_EXTENSIONS


class PlayerAdapter(Protocol):
    name: str
    def command(self, executable: Path, movie: Path, subtitle: Path | None = None) -> list[str]: ...


class MpcBe:
    name = "MPC-BE"

    def command(self, executable, movie, subtitle=None):
        command = [str(Path(executable).resolve()), str(Path(movie).resolve())]
        if subtitle is not None:
            # MPC-BE expects an absolute /sub path.
            command.extend(["/sub", str(Path(subtitle).resolve())])
        return command


# Future adapters can implement IPC separately; opening is not live injection.
ADAPTERS: dict[str, PlayerAdapter] = {"MPC-BE": MpcBe()}


def launch(kind: str, executable: str, movie: str, subtitle: str | None = None):
    exe, video = Path(executable), Path(movie)
    sub = Path(subtitle) if subtitle else None
    if kind not in ADAPTERS:
        raise ValueError("This player has no adapter yet.")
    if not exe.is_file() or exe.suffix.lower() != ".exe":
        raise ValueError("Choose the player executable (.exe).")
    if not video.is_file():
        raise ValueError("Choose an existing video file.")
    if sub is not None and (not sub.is_file() or sub.suffix.lower() not in SUB_EXTENSIONS):
        raise ValueError("Choose an existing subtitle file in a supported format.")
    return subprocess.Popen(ADAPTERS[kind].command(exe, video, sub), shell=False, cwd=exe.parent)
