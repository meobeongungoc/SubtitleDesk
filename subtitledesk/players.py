import subprocess
from pathlib import Path
from typing import Protocol

from .core import SUB_EXTENSIONS


class PlayerAdapter(Protocol):
    name: str
    def command(self, executable: Path, movie: Path, subtitle: Path) -> list[str]: ...


class MpcBe:
    name = "MPC-BE"

    def command(self, executable, movie, subtitle):
        # MPC-BE expects an absolute /sub path.
        return [str(Path(executable).resolve()), str(Path(movie).resolve()),
                "/sub", str(Path(subtitle).resolve())]


# Future adapters can implement IPC separately; opening is not live injection.
ADAPTERS: dict[str, PlayerAdapter] = {"MPC-BE": MpcBe()}


def launch(kind: str, executable: str, movie: str, subtitle: str):
    exe, video, sub = (Path(x) for x in (executable, movie, subtitle))
    if kind not in ADAPTERS:
        raise ValueError("This player has no adapter yet.")
    if not exe.is_file() or exe.suffix.lower() != ".exe":
        raise ValueError("Choose the player executable (.exe).")
    if not video.is_file() or not sub.is_file() or sub.suffix.lower() not in SUB_EXTENSIONS:
        raise ValueError("A valid video and saved subtitle are required.")
    return subprocess.Popen(ADAPTERS[kind].command(exe, video, sub), shell=False, cwd=exe.parent)
