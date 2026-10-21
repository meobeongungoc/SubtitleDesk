"""Real lexicon, subtitle parsing, folder isolation and Anki import contracts."""
import csv
import io
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

from subtitledesk.vocabulary import (Cancelled, Lexicon, anki_text, extract_folder,
                                    export_anki, subtitle_cues)


def srt(text):
    return f'1\n00:00:01,000 --> 00:00:03,000\n{text}\n\n'


class VocabularyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lex = Lexicon()

    def test_real_levels_boundaries_inflections_and_lower_level_exclusion(self):
        matches = list(self.lex.matches("We meticulously compelled the meticulous protagonist's allies to scrutinize it. "
                                        'Apple fine cast ABCXYZ indubitably. These pertain to law; not pertain, to law.'))
        found = [v.term for v in matches]
        for word in ('compel', 'meticulous', 'protagonist', 'scrutinize'):
            self.assertIn(word, found)
        self.assertEqual(found.count('pertain to'), 1)
        self.assertEqual(self.lex.lookup['meticulous'].level, 'C2')
        self.assertEqual(self.lex.lookup['scrutinize'].level, 'C1')
        for excluded in ('apple', 'fine', 'cast', 'abcxyz', 'indubitably'):
            self.assertNotIn(excluded, found)

    def test_vtt_metadata_and_markup(self):
        text = ('WEBVTT\n\nNOTE Scrutinize this metadata\nnot dialogue\n\n'
                'STYLE\n::cue {color: red;}\n\nREGION\nid:meticulous\n\n'
                'cue-id\n00:01.000 --> 00:02.000 align:start\n'
                '<v Narrator><b>We scrutinize</b> &amp; concur.</v>\n')
        self.assertEqual(list(subtitle_cues(text, '.vtt')),
                         [('00:01.000', 'We scrutinize & concur.')])

    def test_ass_drawings_comments_commas_and_reordered_fields(self):
        text = ('[Script Info]\nTitle: meticulous\n[Events]\n'
                'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
                'Comment: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Ignore this\n'
                r'Dialogue: 0,0:01:05.10,0:01:07.80,Default,,0,0,0,,{\i1}We concur{\i0}, sir!{\p1}m 0 0 l 10 10{\p0}\NYes.'+'\n')
        self.assertEqual(list(subtitle_cues(text, '.ass')), [('0:01:05.10', 'We concur, sir! Yes.')])
        reordered = ('[Events]\nFormat: Start, Text, End, Style\n'
                     'Dialogue: 0:00:01.00,We concur, sir!,0:00:02.00,Default\n')
        self.assertEqual(list(subtitle_cues(reordered, '.ssa')), [('0:00:01.00', 'We concur, sir!')])

    def test_recursive_folder_unique_terms_duplicate_copies_and_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            season = root/'Season 1';season.mkdir()
            dialogue = 'We scrutinize this meticulous protagonist. I concur.'
            (season/'Show.S01E01.en.srt').write_text(srt(dialogue), 'utf-8')
            # A duplicate translation track of one episode must not inflate counts.
            (season/'Show.S01E01.en.copy.srt').write_text(srt(dialogue), 'utf-8')
            # Identical words spoken in another episode must still count.
            (season/'Show.S01E02.en.srt').write_text(srt(dialogue), 'utf-8')
            (season/'Show.S01E03.vi.srt').write_text(srt('Tôi rất meticulous và tôi muốn đi về nhà.'), 'utf-8')
            (season/'broken.en.srt').write_text('meticulous is not a subtitle', 'utf-8')
            (root/'not-a-subtitle.txt').write_text(dialogue, 'utf-8')
            report = extract_folder(root, lexicon=self.lex)
            cards = {c.term:c for c in report.cards}
            self.assertEqual(report.found, 5)
            self.assertEqual(report.read, 2)
            self.assertEqual(report.duplicates, 1)
            self.assertEqual(len(report.skipped), 2)
            self.assertEqual(cards['scrutinize'].count, 2)
            self.assertEqual(len(cards['scrutinize'].files), 2)
            self.assertEqual(cards['meticulous'].level, 'C2')
            report = extract_folder(root, levels=('C2',), lexicon=self.lex)
            self.assertTrue(report.cards)
            self.assertTrue(all(c.level == 'C2' for c in report.cards))
            self.assertEqual((season/'Show.S01E01.en.srt').read_text('utf-8'), srt(dialogue))

    def test_anki_three_column_roundtrip_and_never_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'Film.en.srt').write_text(srt('We scrutinize "this" &amp; that. I am meticulous.'), 'utf-8')
            report = extract_folder(root, lexicon=self.lex)
            output = anki_text(report)
            self.assertIn('#separator:Tab\n', output)
            self.assertIn('#tags column:3\n', output)
            records = list(csv.reader(io.StringIO('\n'.join(v for v in output.splitlines() if not v.startswith('#'))), delimiter='\t'))
            self.assertEqual(len(records), len(report.cards))
            self.assertTrue(all(len(r) == 3 for r in records))
            card = next(r for r in records if r[0] == 'scrutinize')
            self.assertIn('&amp;', card[1])
            self.assertIn('&quot;', card[1])
            self.assertIn('00:00:01,000', card[1])
            self.assertEqual(card[2], 'SubtitleDesk CEFR::C1')
            target = root/'Export.txt'
            export_anki(report, target)
            original = target.read_bytes()
            with self.assertRaises(FileExistsError):export_anki(report, target)
            self.assertEqual(target.read_bytes(), original)
            with self.assertRaises(ValueError):export_anki(report, root/'Film.en.srt')

    def test_empty_cancel_invalid_levels_and_file_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertFalse(extract_folder(root, lexicon=self.lex).cards)
            cancel = Event();cancel.set()
            with self.assertRaises(Cancelled):extract_folder(root, cancel=cancel, lexicon=self.lex)
            with self.assertRaises(ValueError):extract_folder(root, levels=('B2',), lexicon=self.lex)
            (root/'oversized.en.srt').write_text(srt('We scrutinize it.'), 'utf-8')
            with patch('subtitledesk.vocabulary.MAX_SUBTITLE', 8):
                report = extract_folder(root, lexicon=self.lex)
            self.assertFalse(report.cards)
            self.assertIn('8 MB', report.skipped[0][1])

    def test_untagged_english_and_non_english(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'English.srt').write_text(srt('We must scrutinize the meticulous protagonist, and I concur.'), 'utf-8')
            (root/'Foreign.srt').write_text(srt('Chúng tôi cùng người meticulous này ra ngoài.'), 'utf-8')
            report = extract_folder(root, lexicon=self.lex)
            self.assertEqual(report.read, 1)
            self.assertEqual(len(report.skipped), 1)


if __name__ == '__main__':
    unittest.main()
