"""Offline, conservative CEFR vocabulary extraction and Anki text export."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
import hashlib
import html
import io
import os
from pathlib import Path
import re
from .core import MAX_SUBTITLE, SUB_EXTENSIONS, decode_subtitle, parse_movie

ASSETS = Path(__file__).parent / 'assets' / 'vocabulary'
TOKEN = re.compile(r"(?<!\w)[a-z]+(?:['-][a-z]+)*(?!\w)", re.I)
TIME = re.compile(r'((?:\d{1,3}:)?\d{2}:\d{2}[.,]\d{3})\s*-->\s*(?:\d{1,3}:)?\d{2}:\d{2}[.,]\d{3}')
COMMON = set('the a an and or but to of in on at for with from is are was were be been being '
             'i you he she it we they me him her us them my your his our their this that these '
             'those do does did have has had not no yes what where when why how who which '
             'can could will would should must if then there here now just so as about all '
             'know think want like get got go come said say tell well really oh don'.split())
NON_ENGLISH = re.compile(r'(?:^|[. _-])(?:vi|vie|vietnamese|fr|fre|fra|french|de|ger|deu|german|'
                        r'es|spa|spanish|it|ita|pt|por|ru|rus|ja|jpn|ko|kor|zh|chi|zho|ar|ara|'
                        r'th|tha|id|ind)(?=$|[. _-])', re.I)
ENGLISH = re.compile(r'(?:^|[. _-])(?:en|eng|english)(?=$|[. _-])', re.I)


class Cancelled(Exception):
    pass


def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise Cancelled('Vocabulary scan cancelled; no export was written.')


def clean_text(value):
    """Remove subtitle markup and ASS vector drawings, retaining dialogue."""
    drawing = False
    output = []
    for part in re.split(r'(\{[^}]*\})', value):
        if part.startswith('{') and part.endswith('}'):
            mode = re.search(r'\\p(\d+)\b', part)
            if mode:
                drawing = int(mode[1]) > 0
        elif not drawing:
            output.append(part)
    value = ''.join(output)
    value = re.sub(r'\\[Nnh]', ' ', value)
    value = re.sub(r'<[^>]*>', '', value)
    return ' '.join(html.unescape(value).split())


def subtitle_cues(text, suffix):
    """Yield (timestamp, dialogue); never treat headers/styles as speech."""
    if suffix.lower() in {'.ass', '.ssa'}:
        section = ''
        columns = ['layer', 'start', 'end', 'style', 'name', 'marginl', 'marginr', 'marginv', 'effect', 'text']
        for line in text.splitlines():
            line = line.strip()
            if line.startswith('['):
                section = line.casefold()
            elif section == '[events]' and line.lower().startswith('format:'):
                columns = [v.strip().lower() for v in line.split(':', 1)[1].split(',')]
            elif section == '[events]' and line.lower().startswith('dialogue:'):
                if 'text' not in columns or 'start' not in columns:
                    continue
                text_index = columns.index('text')
                prefix = line.split(':', 1)[1].lstrip().split(',', text_index)
                if len(prefix) != text_index + 1:
                    continue
                tail = prefix[-1].rsplit(',', len(columns) - text_index - 1) if text_index < len(columns)-1 else [prefix[-1]]
                fields = prefix[:-1] + tail
                if len(fields) != len(columns):
                    continue
                stamp = fields[columns.index('start')].strip()
                if not re.fullmatch(r'\d+:\d{2}:\d{2}\.\d{2,3}', stamp):
                    continue
                dialogue = clean_text(fields[text_index])
                if dialogue:
                    yield stamp, dialogue
        return
    for block in re.split(r'\n\s*\n', text.replace('\r\n', '\n').replace('\r', '\n')):
        lines = block.strip().splitlines()
        if not lines or re.match(r'^(?:NOTE(?:\s|$)|STYLE$|REGION$)', lines[0]):
            continue
        stamp, parts = None, []
        for index, line in enumerate(lines):
            match = TIME.search(line)
            if match:
                if stamp and parts:
                    dialogue = clean_text(' '.join(parts))
                    if dialogue:
                        yield stamp, dialogue
                stamp, parts = match[1], []
            elif stamp and not (line.strip().isdigit() and index+1 < len(lines) and TIME.search(lines[index+1])):
                parts.append(line)
        if stamp and parts:
            dialogue = clean_text(' '.join(parts))
            if dialogue:
                yield stamp, dialogue


def forms(word, pos):
    """Regular inflections only; ambiguous aliases are discarded by the lexicon."""
    result = {word}
    if pos not in {'noun', 'verb', 'adjective'} or not re.fullmatch('[a-z]+', word):
        return result
    if pos in {'noun', 'verb'}:
        result.add(word + ('es' if word.endswith(('s', 'x', 'z', 'ch', 'sh', 'o')) else 's'))
        if re.search('[^aeiou]y$', word):
            result.add(word[:-1] + 'ies')
    if pos == 'verb':
        if re.search('[^aeiou]y$', word):
            result.add(word[:-1] + 'ied')
        else:
            result.add(word + ('d' if word.endswith('e') else 'ed'))
        result.add(word[:-2] + 'ying' if word.endswith('ie') else
                   word[:-1] + 'ing' if word.endswith('e') and not word.endswith(('ee', 'ye', 'oe')) else word + 'ing')
        if re.search('[^aeiou][aeiou][^aeiouwxy]$', word):
            result.update({word + word[-1] + 'ed', word + word[-1] + 'ing'})
    if pos == 'adjective':
        if re.search('[^aeiou]y$', word):
            result.update({word[:-1]+'ier', word[:-1]+'iest'})
        elif word.endswith('e'):
            result.update({word+'r', word+'st'})
        elif len(word) <= 6:
            result.update({word+'er', word+'est'})
    return result


@dataclass
class Entry:
    term: str
    level: str
    pos: set = field(default_factory=set)


class Lexicon:
    def __init__(self, directory=ASSETS):
        directory = Path(directory)
        self.basic = set()
        self.entries = {}
        variants = {}
        with (directory/'cefrj-vocabulary-profile-1.5.csv').open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                for term in row['headword'].lower().split('/'):
                    self.basic.add(term.strip())
                    self.basic.update(forms(term.strip(), row['pos']))
        with (directory/'octanove-vocabulary-profile-c1c2-1.0.csv').open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                aliases = [v.strip().lower() for v in row['headword'].split('/') if v.strip()]
                if row['CEFR'] not in {'C1', 'C2'} or any(v in self.basic for v in aliases):
                    continue  # Exclude lower-level homographs rather than guess the advanced sense.
                canonical = aliases[0]
                entry = self.entries.setdefault(canonical, Entry(canonical, row['CEFR']))
                entry.level = min(entry.level, row['CEFR'])
                entry.pos.add(row['pos'])
                for alias in aliases:
                    bits = alias.split()
                    first_forms = forms(bits[0], row['pos']) if len(bits) == 1 or row['pos'] == 'verb' else {bits[0]}
                    for first in first_forms:
                        key = ' '.join([first] + bits[1:])
                        variants.setdefault(key, set()).add(canonical)
        self.lookup = {key: self.entries[next(iter(values))] for key, values in variants.items()
                       if len(values) == 1 and key not in self.basic}
        # An exact headword wins over another word's generated inflection.
        self.lookup.update(self.entries)
        self.phrases = {}
        for key in self.lookup:
            if ' ' in key:
                self.phrases.setdefault(key.split()[0], []).append(key.split())

    def matches(self, text):
        normalized = text.lower().replace('’', "'").replace('‑', '-').replace('‐', '-')
        tokens = list(TOKEN.finditer(normalized))
        for index, token in enumerate(tokens):
            word = token[0]
            if word.endswith("'s"):
                word = word[:-2]
            if word in self.lookup:
                yield self.lookup[word]
            for phrase in self.phrases.get(word, ()):
                following = tokens[index:index+len(phrase)]
                if len(following) == len(phrase) and [m[0] for m in following] == phrase and all(
                        normalized[a.end():b.start()].isspace() for a, b in zip(following, following[1:])):
                    yield self.lookup[' '.join(phrase)]


def english_subtitle(path, cues):
    if NON_ENGLISH.search(path.stem) and not ENGLISH.search(path.stem):
        return False
    sample = ' '.join(text for _, text in cues[:150])[:16000]
    letters = [c for c in sample if c.isalpha()]
    if not letters or sum(ord(c) > 127 for c in letters) / len(letters) > .06:
        return False
    if ENGLISH.search(path.stem):
        return True
    words = TOKEN.findall(sample.lower())[:500]
    common = sum(word in COMMON for word in words)
    return common >= 2 and common / max(1, len(words)) >= .08


@dataclass
class Card:
    term: str
    level: str
    pos: tuple
    count: int = 0
    examples: list = field(default_factory=list)
    files: set = field(default_factory=set)


@dataclass
class Report:
    root: Path
    cards: list = field(default_factory=list)
    found: int = 0
    read: int = 0
    duplicates: int = 0
    skipped: list = field(default_factory=list)


def extract_folder(folder, levels=('C1', 'C2'), cancel=None, progress=None, lexicon=None):
    folder = Path(folder)
    if folder.is_symlink() or getattr(folder, 'is_junction', lambda: False)() or not folder.is_dir():
        raise ValueError('Choose a real movie folder, not a shortcut or linked folder.')
    levels = set(levels)
    if not levels or not levels <= {'C1', 'C2'}:
        raise ValueError('Choose C1, C2, or both.')
    root = folder.resolve()
    report = Report(root)
    paths = []
    def walk_error(error):
        report.skipped.append((str(error.filename), 'Folder could not be read'))
    for directory, dirs, names in os.walk(root, followlinks=False, onerror=walk_error):
        check_cancel(cancel)
        dirs[:] = sorted(d for d in dirs if not (Path(directory)/d).is_symlink()
                         and not getattr(Path(directory)/d, 'is_junction', lambda: False)())
        for name in sorted(names):
            path = Path(directory)/name
            if path.suffix.lower() in SUB_EXTENSIONS and not path.is_symlink():
                paths.append(path)
                if len(paths) > 5000:
                    raise ValueError('More than 5,000 subtitles. Choose a smaller movie folder.')
    report.found = len(paths)
    lexicon = lexicon or Lexicon()
    cards, seen, total = {}, set(), 0
    for index, path in enumerate(paths):
        check_cancel(cancel)
        relative = str(path.relative_to(root))
        if progress:
            progress(index+1, len(paths), relative)
        try:
            with path.open('rb') as stream:
                data = stream.read(MAX_SUBTITLE+1)
            if len(data) > MAX_SUBTITLE:
                raise ValueError('Subtitle exceeds 8 MB')
            total += len(data)
            if total > 128 * 1024 * 1024:
                raise ValueError('Folder exceeds the 128 MB subtitle limit. Choose a smaller folder.')
            try:
                text = decode_subtitle(data)
            except ValueError:
                # Legacy Windows subtitles; core validation still rejects binary data.
                text = decode_subtitle(data, 'cp1252')
            cues = list(subtitle_cues(text, path.suffix))
            if not cues:
                raise ValueError('No readable dialogue cues')
            if not english_subtitle(path, cues):
                report.skipped.append((relative, 'Not identified as English'))
                continue
        except (OSError, ValueError) as exc:
            if total > 128 * 1024 * 1024:
                raise ValueError('Folder exceeds the 128 MB subtitle limit. Choose a smaller folder.') from exc
            report.skipped.append((relative, str(exc)))
            continue
        digest = hashlib.sha256('\n'.join(t.casefold() for _, t in cues).encode('utf-8')).digest()
        movie = parse_movie(path.name)
        episode = (movie.season, movie.episode) if movie.season and movie.episode else None
        duplicate_key = (episode, digest)
        if duplicate_key in seen:
            report.duplicates += 1
            continue
        seen.add(duplicate_key)
        report.read += 1
        for stamp, dialogue in cues:
            check_cancel(cancel)
            for entry in lexicon.matches(dialogue):
                if entry.level not in levels:
                    continue
                card = cards.setdefault(entry.term, Card(entry.term, entry.level, tuple(sorted(entry.pos))))
                card.count += 1
                card.files.add(relative)
                example = (dialogue[:700], relative, stamp)
                if len(card.examples) < 3 and example not in card.examples:
                    card.examples.append(example)
    check_cancel(cancel)
    report.cards = sorted(cards.values(), key=lambda c: (-c.count, c.term))
    return report


def anki_text(report):
    """Two Basic fields plus a tags column; HTML escaped and CSV quoted."""
    output = io.StringIO(newline='')
    output.write('#separator:Tab\n#html:true\n#columns:Front\tBack\tTags\n#tags column:3\n')
    output.write('# CEFR annotations: Octanove Labs, Vocabulary Profile C1/C2 v1.0; CC BY-SA 4.0\n')
    output.write('# https://github.com/openlanguageprofiles/olp-en-cefrj\n')
    output.write('# https://creativecommons.org/licenses/by-sa/4.0/\n')
    output.write('# A1-B2 exclusion: CEFR-J Wordlist v1.5, Yukio Tono, TUFS; citation required\n')
    output.write('# Levels are list-based estimates, not context-sense judgments. Unknown words excluded.\n')
    output.write('# Dataset license covers CEFR annotations; subtitle excerpts retain their original rights.\n')
    writer = csv.writer(output, delimiter='\t', lineterminator='\n')
    for card in report.cards:
        back = f'<b>{card.level}</b> · {html.escape(", ".join(card.pos))}'
        for dialogue, source, stamp in card.examples:
            back += f'<br><br>{html.escape(dialogue)}<br><small>{html.escape(source)} · {html.escape(stamp)}</small>'
        back += f'<br><br>Occurrences: {card.count} · Subtitle files: {len(card.files)}'
        writer.writerow([card.term, back, f'SubtitleDesk CEFR::{card.level}'])
    return output.getvalue()


def export_anki(report, path):
    path = Path(path)
    if path.suffix.lower() != '.txt':
        raise ValueError('Choose a .txt output filename.')
    if not report.cards:
        raise ValueError('There are no C1/C2 vocabulary cards to export.')
    # Exclusive creation protects against changes between the save dialog and writing.
    with path.open('xb') as stream:
        stream.write(anki_text(report).encode('utf-8'))
        stream.flush()
        os.fsync(stream.fileno())
