"""Folder planning, conservative episode matching and non-overwriting sidecars."""
from dataclasses import dataclass, field, replace
from difflib import SequenceMatcher
import os
from pathlib import Path
import re
from .core import Movie, VIDEO_EXTENSIONS, SUB_EXTENSIONS, normalized, parse_movie, decode_subtitle, save_subtitle
from .providers import Result


@dataclass
class Episode:
    path: Path
    movie: Movie
    enabled: bool = True
    state: str = "Not searched"
    candidates: list = field(default_factory=list)
    selected: Result | None = None
    torrent_hash: str = ""
    file_index: int = -1
    progress: float = 1.0
    saved: str = ""


def identify(path: Path, title="", season="") -> Movie:
    value = parse_movie(path.name)
    clean = re.sub(r"[._]", " ", path.stem)
    # Multi-episode files need manual handling, never silently pick the first episode.
    if re.search(r"(?i)S\d+E\d+(?:E\d+|[- ]+E?\d+)\b|(?:tập|tap|ep(?:isode)?)\s*\d+\s*-\s*\d+", clean):
        return replace(value, title=title or value.title, season="", episode="")
    if not value.episode:
        match = re.search(r"(?i)\b(?:tập|tap|ep(?:isode)?|e)\s*(\d{1,3})\b", clean)
        if match:
            value = replace(value, title=clean[:match.start()].strip(" -[]") or value.title,
                            episode=str(int(match[1])))
    folder_season = re.search(r"(?i)\b(?:season|mùa|mua|s)\s*(\d{1,2})\b",
                             re.sub(r"[._]", " ", path.parent.name))
    return replace(value, title=title or value.title,
                   season=season or value.season or (str(int(folder_season[1])) if folder_season else ""))


def existing_subtitle(path: Path):
    prefix = path.stem.casefold()
    return next((p for p in path.parent.iterdir() if p.is_file() and p.suffix.lower() in SUB_EXTENSIONS
                 and (p.stem.casefold() == prefix or p.stem.casefold().startswith(prefix + "."))), None)


def scan_folder(folder, recursive=False, title="", season=""):
    root = Path(folder).resolve()
    rows = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(directory) / d).is_symlink()
                   and not getattr(Path(directory) / d, "is_junction", lambda: False)()]
        for name in sorted(files, key=str.casefold):
            path = Path(directory) / name
            if path.suffix.lower() not in VIDEO_EXTENSIONS or path.is_symlink():
                continue
            movie = identify(path, title, season)
            found = existing_subtitle(path)
            state = "Subtitle exists" if found else ("Edit season/episode" if not movie.season or not movie.episode else "Not searched")
            rows.append(Episode(path, movie, not bool(found), state))
            if len(rows) >= 5000:
                raise ValueError("Thư mục có hơn 5.000 video; hãy chọn thư mục phim cụ thể hơn.")
        if not recursive:
            break
    return sorted(rows, key=lambda r: (normalized(r.movie.title), int(r.movie.season or 0),
                                       int(r.movie.episode or 0), str(r.path)))


def result_episode(result):
    parsed = parse_movie(result.release)
    return result.season or parsed.season, result.episode or parsed.episode


def exact_filename(movie_path, result):
    """Only actual subtitle filenames qualify, never a fuzzy release/title score."""
    name = Path(result.filename.replace("\\", "/"))
    if result.season_pack or not result.filename:
        return False
    # OpenSubtitles can return file_name without its subtitle extension.
    stem = name.stem if name.suffix.lower() in SUB_EXTENSIONS else name.name
    return (name.suffix.lower() not in {".zip", ".rar", ".7z", ".exe"}
            and stem.casefold() == Path(movie_path).stem.casefold())


def rank(movie, result, language):
    if result.language != language:
        return None
    explicit = identify(Path(result.release))
    if not result.season_pack and ((explicit.season and int(explicit.season) != int(movie.season))
                                  or (explicit.episode and int(explicit.episode) != int(movie.episode))):
        return None
    season, episode = result_episode(result)
    if not season.isdecimal() or (not episode.isdecimal() and not result.season_pack):
        return None
    if int(season) != int(movie.season) or (not result.season_pack and int(episode) != int(movie.episode)):
        return None
    parsed = parse_movie(result.release)
    title = parse_movie(result.title).title
    similarity = max(SequenceMatcher(None, normalized(movie.title), normalized(title)).ratio(),
                     SequenceMatcher(None, normalized(movie.title), normalized(parsed.title)).ratio())
    if similarity < .65:
        return None
    score = round(80 * similarity)
    if movie.release and parsed.release:
        score += round(20 * SequenceMatcher(None, normalized(movie.release), normalized(parsed.release)).ratio())
    return score


def select_file(movie, result, candidates):
    matches = []
    for name, data in candidates:
        info = identify(Path(name))
        if info.season and info.episode:
            if (int(info.season), int(info.episode)) == (int(movie.season), int(movie.episode)):
                matches.append((name, data))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError("ZIP contains multiple files for this episode; choose a file in Single file / Preview.")
    if len(candidates) == 1 and not result.season_pack:
        info = identify(Path(candidates[0][0]))
        if info.season or info.episode:
            raise ValueError("Subtitle filename does not confirm the episode; check it manually.")
        season, episode = result_episode(result)
        if (season.isdecimal() and episode.isdecimal()
                and (int(season), int(episode)) == (int(movie.season), int(movie.episode))):
            return candidates[0]
    raise ValueError("Could not identify the correct episode inside the ZIP; choose it manually.")


def save_episode(row, name, data, encoding="auto"):
    if not row.path.is_file():
        raise ValueError("The video file is not available at its current location.")
    existing = existing_subtitle(row.path)
    if existing:
        return None
    decode_subtitle(data, encoding)
    # Exactly the movie stem, no language suffix by default.
    destination = row.path.with_suffix(Path(name).suffix.lower())
    save_subtitle(destination, data, overwrite=False)
    return destination
