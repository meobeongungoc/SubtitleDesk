from __future__ import annotations

import io
import os
import re
import stat
import tempfile
import unicodedata
import zipfile
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path, PurePosixPath

SUB_EXTENSIONS = {".srt", ".ass", ".ssa", ".vtt"}
VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".webm", ".wmv", ".ts"}
MAX_SUBTITLE = 8 * 1024 * 1024
MAX_ARCHIVE = 32 * 1024 * 1024
MAX_EXPANDED = 64 * 1024 * 1024
MAX_ENTRIES = 200


@dataclass(frozen=True)
class Movie:
    title: str
    year: str = ""
    season: str = ""
    episode: str = ""
    release: str = ""


def parse_movie(value: str) -> Movie:
    name = value.replace("\\", "/").rsplit("/", 1)[-1]
    if Path(name).suffix.lower() in VIDEO_EXTENSIONS | SUB_EXTENSIONS:
        name = name[:name.rfind(".")]
    name = re.sub(r"[._]+", " ", name).strip()
    ep = re.search(r"\bS(\d{1,2})\s*E(\d{1,3})\b|\b(\d{1,2})x(\d{1,3})\b", name, re.I)
    # A leading year-shaped token can be the movie title (1917, 2001, ...).
    year = next((m for m in re.finditer(r"\b(19\d{2}|20\d{2})\b", name) if m.start() > 0), None)
    release = re.search(
        r"\b(?:2160p|1080[pi]|720p|480p|WEB[- ]?DL|WEBRip|BluRay|BDRip|"
        r"HDTV|DVDRip|REMUX|HEVC|x26[45]|h26[45])\b", name, re.I)
    boundaries = [m.start() for m in (ep, year, release) if m and m.start() > 0]
    title = name[:min(boundaries)] if boundaries else name
    title = title.strip(" -([])")
    return Movie(title or name, year.group(1) if year else "",
                 str(int(ep.group(1) or ep.group(3))) if ep else "",
                 str(int(ep.group(2) or ep.group(4))) if ep else "",
                 name[release.start():].strip() if release else "")


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower().replace("đ", "d"))
    return " ".join(re.sub(r"[^\w]+", " ", "".join(
        c for c in value if not unicodedata.combining(c))).split())


def match_score(movie: Movie, release: str, title: str, language: str,
                languages: list[str]) -> tuple[int, str]:
    candidate = parse_movie(release or title)
    similarity = SequenceMatcher(None, normalized(movie.title), normalized(candidate.title)).ratio()
    score = round(50 * similarity)
    reasons = [f"Title similarity {round(similarity * 100)}%"]
    for label, wanted, got, bonus, penalty in (
        ("year", movie.year, candidate.year, 15, 25),
        ("season", movie.season, candidate.season, 10, 35),
        ("episode", movie.episode, candidate.episode, 15, 50),
    ):
        if wanted and got:
            same = int(wanted) == int(got)
            score += bonus if same else -penalty
            reasons.append(f"{'Same' if same else 'Different'} {label}")
        elif wanted:
            reasons.append(f"Unknown {label}")
    if movie.release and candidate.release:
        score += round(5 * SequenceMatcher(None, normalized(movie.release),
                                           normalized(candidate.release)).ratio())
    if language in languages:
        score += max(1, 5 - languages.index(language))
        reasons.append(f"Preferred language: {language}")
    return max(0, min(score, 100)), "; ".join(reasons)


def decode_subtitle(data: bytes, encoding: str = "auto") -> str:
    if not data or len(data) > MAX_SUBTITLE:
        raise ValueError("Subtitle is empty or exceeds 8 MB.")
    if encoding != "auto":
        text = data.decode(encoding)
    elif data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16")
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Unknown encoding. Try cp1258 or cp1252 to preview.") from exc
    if "\x00" in text or any(ord(c) < 9 for c in text):
        raise ValueError("The file contains binary data, not a supported text subtitle.")
    if not ("-->" in text or re.search(r"(?im)^\s*(\[Script Info\]|Dialogue:)", text)):
        raise ValueError("No SRT/VTT/ASS/SSA structure found in the file.")
    return text


def unpack_subtitles(name: str, data: bytes) -> list[tuple[str, bytes]]:
    """Read into memory; never extract archive paths onto the filesystem."""
    if len(data) > MAX_ARCHIVE:
        raise ValueError("Download/import exceeds 32 MB.")
    ext = Path(name).suffix.lower()
    if ext in SUB_EXTENSIONS:
        if len(data) > MAX_SUBTITLE:
            raise ValueError("Subtitle exceeds 8 MB.")
        return [(Path(name).name, data)]
    if ext != ".zip":
        raise ValueError("Supported: SRT, ASS, SSA, VTT and ZIP. RAR/7z are not supported.")
    output = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_ENTRIES or sum(x.file_size for x in entries) > MAX_EXPANDED:
            raise ValueError("ZIP contains too many files or exceeds the expanded size limit.")
        for item in entries:
            path = PurePosixPath(item.filename.replace("\\", "/"))
            mode = item.external_attr >> 16
            if (path.is_absolute() or ".." in path.parts or ":" in item.filename
                    or stat.S_ISLNK(mode)):
                raise ValueError("ZIP contains an unsafe path or link.")
            if item.flag_bits & 1:
                raise ValueError("Password-protected ZIP files are not supported.")
            if item.is_dir() or path.suffix.lower() not in SUB_EXTENSIONS:
                continue
            if item.file_size > MAX_SUBTITLE:
                raise ValueError("A subtitle in the ZIP exceeds 8 MB.")
            if item.file_size > 1024 * 1024 and item.file_size / max(item.compress_size, 1) > 200:
                raise ValueError("ZIP compression ratio is suspiciously high.")
            with archive.open(item) as stream:
                content = stream.read(MAX_SUBTITLE + 1)
            if len(content) > MAX_SUBTITLE:
                raise ValueError("Expanded subtitle exceeds the size limit.")
            output.append((str(path), content))
    if not output:
        raise ValueError("ZIP contains no supported subtitles.")
    return output


def save_subtitle(path: Path, data: bytes, overwrite: bool = False) -> None:
    path = Path(path)
    if path.suffix.lower() not in SUB_EXTENSIONS:
        raise ValueError("Save only .srt, .ass, .ssa or .vtt files.")
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        raise ValueError("Writing through file links is not allowed.")
    if overwrite:
        # Replace the directory entry atomically, never truncate a hardlink target.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".subtitledesk-",
                                             suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    else:
        # Exclusive creation prevents accidental overwrite after a UI check.
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
