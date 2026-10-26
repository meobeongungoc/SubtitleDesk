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
    saved: str = ""
    saved_languages: dict = field(default_factory=dict)
    ambiguous: bool = False
    saved_result_ids: dict = field(default_factory=dict)


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


def subtitle_index(directory):
    """Enumerate each directory once; never follow a subtitle symlink."""
    return sorted((p for p in Path(directory).iterdir()
                   if p.suffix.lower() in SUB_EXTENSIONS and p.is_file() and not p.is_symlink()),
                  key=lambda p: p.name.casefold())


def existing_subtitle(path: Path, language=None, index=None):
    prefix = path.stem.casefold()
    candidates = subtitle_index(path.parent) if index is None else index
    for item in candidates:
        stem = item.stem.casefold()
        if language:
            if stem == prefix + '.' + language.lower() or stem.startswith(prefix + '.' + language.lower() + '.'):
                return item
        elif stem == prefix or stem.startswith(prefix + '.'):
            return item
    return None


def saved_tracks(path, languages, index=None):
    return {language: str(found) for language in languages
            if (found := existing_subtitle(path, language, index))}


def scan_folder(folder, recursive=False, title="", season="", languages=("vi", "en")):
    root = Path(folder).resolve()
    rows = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(directory) / d).is_symlink()
                   and not getattr(Path(directory) / d, "is_junction", lambda: False)()]
        subtitles = subtitle_index(directory)
        for name in sorted(files, key=str.casefold):
            path = Path(directory) / name
            if path.suffix.lower() not in VIDEO_EXTENSIONS or path.is_symlink():
                continue
            movie = identify(path, title, season)
            tracks = saved_tracks(path, languages, subtitles)
            ambiguous = bool(re.search(r"(?i)S\d+E\d+(?:E\d+|[- ]+E?\d+)\b|(?:tập|tap|ep(?:isode)?)\s*\d+\s*-\s*\d+", path.stem))
            incomplete = bool(movie.season) != bool(movie.episode)
            state = "Subtitles exist" if all(lang in tracks for lang in languages) else (
                "Edit season/episode" if ambiguous or incomplete else "Not searched")
            rows.append(Episode(path, movie, not all(lang in tracks for lang in languages), state,
                                saved_languages=tracks, ambiguous=ambiguous))
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
    if not movie.season and not movie.episode:
        if result.season_pack or result.season or result.episode:
            raise ValueError("An episode or season pack cannot be applied to a standalone movie.")
        eligible = [(name, data) for name, data in candidates
                    if not identify(Path(name)).season and not identify(Path(name)).episode]
        if len(eligible) == len(candidates) == 1:
            return eligible[0]
        exact = [(name, data) for name, data in eligible
                 if Path(name).name.casefold() == Path(result.filename).name.casefold()]
        if len(exact) == 1:
            return exact[0]
        raise ValueError("Archive contains multiple or episodic subtitles; use Import local subtitle / ZIP in Settings.")
    if not movie.season.isdecimal() or not movie.episode.isdecimal():
        raise ValueError("Confirm numeric season and episode before applying this subtitle.")
    matches = []
    for name, data in candidates:
        info = identify(Path(name))
        if info.season and info.episode:
            if (int(info.season), int(info.episode)) == (int(movie.season), int(movie.episode)):
                matches.append((name, data))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError("ZIP contains multiple files for this episode; use Import local subtitle / ZIP in Settings.")
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
    language = row.selected.language if row.selected else None
    existing = existing_subtitle(row.path, language)
    if existing:
        return None
    decode_subtitle(data, encoding)
    if language and not re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})?", language):
        raise ValueError("Unsupported subtitle language code.")
    suffix = ('.' + language if language else '') + Path(name).suffix.lower()
    destination = row.path.with_name(row.path.stem + suffix)
    save_subtitle(destination, data, overwrite=False)
    return destination
