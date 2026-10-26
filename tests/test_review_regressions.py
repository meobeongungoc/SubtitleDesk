"""Regression coverage for reviewed failures and the single-window workflow."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from subtitledesk.batch import (Episode, existing_subtitle, identify, scan_folder,
                               select_file, save_episode)
from subtitledesk.gui import Application
from subtitledesk.providers import Capabilities, Page, Registry, Result, SearchEngine
from subtitledesk.storage import CredentialError, SecretStore

SRT = b"1\n00:00:01,000 --> 00:00:03,000\nWe scrutinize a meticulous protagonist.\n"


class ReviewRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name).resolve()
        self.app = Application(self.home, hidden=True)
        self.app.root.withdraw()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.app.close)

    def wait(self, predicate):
        deadline = time.monotonic() + 8
        while predicate() and time.monotonic() < deadline:
            self.app.root.update()
            time.sleep(.01)
        self.assertFalse(predicate())

    def test_busy_drop_and_stale_results_never_replace_current_movie(self):
        self.assertEqual(self.app.root.state(), "withdrawn")
        library = self.app.library
        first = self.home/'First.S01E01.mkv'; first.write_bytes(b'fixture')
        other = self.home/'Other.S01E01.mkv'; other.write_bytes(b'fixture')
        library.set_rows(scan_folder(self.home))
        original_paths = [r.path for r in library.rows]
        library.batch_busy = True
        self.app.drop(SimpleNamespace(data=str(other), action='copy'))
        self.assertEqual([r.path for r in library.rows], original_paths)
        library.batch_busy = False
        old_generation = library.generation
        old = library.rows[0]
        library.set_rows([Episode(other, identify(other))])
        generation = library.generation
        library.events.put(('row', old_generation, 0, old.path, old))
        library.events.put(('row', generation, 0, first, old))
        library.events.put(('row', generation, 100, other, old))
        discovery=[]
        library.events.put(('callback', None, lambda value: discovery.append(value), 'independent discovery'))
        valid = replace(library.rows[0], state='Current update')
        library.events.put(('row', generation, 0, other, valid))
        library.poll()
        self.assertEqual(library.rows[0].path, other)
        self.assertEqual(library.rows[0].state, 'Current update')
        self.assertEqual(discovery, ['independent discovery'])
        self.assertTrue(self.app.root.tk.call('after', 'info'))

    def test_film_and_two_languages_auto_download_without_overwrite(self):
        video = self.home/'Arrival.2016.1080p.mkv'; video.write_bytes(b'fixture')
        unknown = video.with_suffix('.srt'); unknown.write_bytes(b'Existing unknown-language file')
        class Source:
            capabilities = Capabilities('subdl', 'Fixture', min_interval=0)
            downloads = []
            def search(self, query, cursor, context):
                return Page([Result('subdl', lang, 'Arrival', lang, 'Arrival.2016.1080p',
                                    filename='Arrival.2016.1080p.srt') for lang in query.languages])
            def download(self, result, context):
                self.downloads.append(result.language)
                return result.filename, SRT
        source = Source()
        registry = Registry(); registry.add(source)
        self.app.registry = registry
        self.app.engine = SearchEngine(registry)
        self.app.enabled = {'subdl': tk.BooleanVar(master=self.app.root, value=True)}
        library = self.app.library
        library.set_rows(scan_folder(self.home))
        with patch('tkinter.messagebox.askyesno', side_effect=AssertionError('Unexpected popup')):
            library.search_batch()
            self.wait(lambda: library.batch_busy)
        self.assertEqual(set(source.downloads), {'vi','en'})
        self.assertEqual(set(library.rows[0].saved_languages), {'vi','en'})
        self.assertEqual(video.with_suffix('.vi.srt').read_bytes(), SRT)
        self.assertEqual(video.with_suffix('.en.srt').read_bytes(), SRT)
        self.assertEqual(unknown.read_bytes(), b'Existing unknown-language file')
        library.search_batch(); self.wait(lambda: library.batch_busy)
        self.assertEqual(len(source.downloads), 2)
        with patch('subtitledesk.players.launch') as launch:
            library.open_episode()
            self.assertIn(launch.call_args.args[3], library.rows[0].saved_languages.values())

    def test_movie_selection_rejects_series_and_ambiguous_archives(self):
        movie = identify(Path('Arrival.2016.mkv'))
        result = Result('subdl','film','Arrival','en',filename='Arrival.2016.srt')
        self.assertEqual(select_file(movie,result,[('Arrival.2016.srt',SRT)])[1],SRT)
        with self.assertRaises(ValueError):
            select_file(movie,result,[('Show.S01E01.srt',SRT)])
        with self.assertRaises(ValueError):
            select_file(movie,replace(result,filename=''),[('one.srt',SRT),('two.srt',SRT)])
        with self.assertRaises(ValueError):
            select_file(identify(Path('Show.S01E01E02.mkv')),replace(result,season_pack=True),[('Show.S01E01.srt',SRT)])
        video=self.home/'Show.S01E01E02.mkv';video.write_bytes(b'fixture')
        self.assertTrue(scan_folder(self.home)[0].ambiguous)

    def test_scan_indexes_a_directory_once_and_keeps_missing_language_enabled(self):
        for i in range(1,51):
            (self.home/f'Show.S01E{i:02}.mkv').write_bytes(b'fixture')
        (self.home/'Show.S01E01.vi.srt').write_bytes(SRT)
        original = Path.iterdir
        calls=[]
        def counted(path):
            calls.append(path)
            return original(path)
        with patch.object(Path,'iterdir',counted):
            rows=scan_folder(self.home)
        self.assertEqual(len(rows),50)
        self.assertEqual(calls,[self.home])
        self.assertTrue(rows[0].enabled)
        self.assertIsNone(existing_subtitle(rows[0].path,'en'))
        self.assertFalse(scan_folder(self.home,languages=('vi',))[0].enabled)

    def test_redraw_updates_rows_without_recreating_or_losing_sort(self):
        for i in (1,2): (self.home/f'Show.S01E{i:02}.mkv').write_bytes(b'fixture')
        library=self.app.library;library.set_rows(scan_folder(self.home))
        view=library.batch_table
        view.selection_set('1');view.focus('1');view.move('1','',0)
        before=view.get_children()
        library.rows[1].state='Changed'
        with patch.object(view,'delete',side_effect=AssertionError('No row deletion expected')):
            library.redraw()
        self.assertEqual(view.get_children(),before)
        self.assertEqual(view.selection(),('1',))
        self.assertEqual(view.focus(),'1')
        self.assertEqual(view.set('1','state'),'Changed')

    def test_auxiliary_pages_and_editor_stay_in_the_root_window(self):
        self.app.show_appearance()
        self.assertEqual(self.app.pages.select(),str(self.app.appearance_window))
        self.app.show_tools(self.app.sources)
        self.app.show_tools(self.app.workflow)
        self.app.library.show_vocabulary()
        vocabulary=self.app.library.vocabulary_window
        self.assertIs(vocabulary.window.winfo_toplevel(), self.app.root)
        video=self.home/'Show.S01E01.mkv';video.write_bytes(b'fixture')
        self.app.library.set_rows(scan_folder(self.home))
        self.app.library.edit()
        self.assertEqual(self.app.pages.select(),str(self.app.editor_page))
        self.app.close_editor()
        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)
        self.assertFalse(any(isinstance(w,tk.Toplevel) for w in descendants(self.app.root)))
        self.assertEqual([self.app.pages.tab(t,'text') for t in self.app.pages.tabs()],
                         ['Library','Vocabulary','Settings','Appearance'])

    def test_overwrite_requires_inline_choice_and_captures_original_bytes(self):
        target=self.home/'existing.srt';target.write_bytes(SRT)
        self.app.selected_data=SRT+b'original preview'
        self.app.selected_name='subtitle.srt'
        with patch('subtitledesk.gui.filedialog.asksaveasfilename',return_value=str(target)), \
             patch('tkinter.messagebox.askyesno',side_effect=AssertionError('No popup')):
            self.assertIsNone(self.app.save())
            self.assertEqual(target.read_bytes(),SRT)
            self.app.cancel_confirmation()
            self.assertEqual(target.read_bytes(),SRT)
            self.app.save()
            self.app.selected_data=b'new unrelated preview'
            self.app.accept_confirmation()
        self.assertEqual(target.read_bytes(),SRT+b'original preview')

    def test_vocabulary_export_keeps_ui_responsive_and_blocks_duplicate_clicks(self):
        from subtitledesk.vocabulary import Card, Report
        self.app.library.show_vocabulary()
        vocabulary=self.app.library.vocabulary_window
        vocabulary.report=Report(self.home,cards=[Card('meticulous','C2',('adjective',),count=1,
            examples=[('A meticulous plan.','Episode.en.srt','00:00:01,000')])])
        target=self.home/'Cards.txt'
        started,release=threading.Event(),threading.Event()
        threads=[]
        def slow_cleanup(report, **kwargs):
            threads.append(threading.get_ident())
            started.set()
            if not release.wait(5): raise AssertionError('Fixture release timed out')
            return 0,[]
        try:
            with patch('subtitledesk.vocabulary_ui.filedialog.asksaveasfilename',return_value=str(target)), \
                 patch('subtitledesk.vocabulary_ui.recycle_scanned_subtitles',side_effect=slow_cleanup) as recycle:
                vocabulary.export()
                self.assertTrue(started.wait(2))
                self.assertTrue(vocabulary.busy)
                heartbeat=[]
                self.app.root.after(0,lambda:heartbeat.append(True))
                self.app.root.update()
                self.assertTrue(heartbeat)
                vocabulary.export()
                self.assertEqual(recycle.call_count,1)
                self.assertNotEqual(threads[0],threading.get_ident())
                self.assertTrue(target.read_text('utf-8').startswith('#separator:Tab'))
                release.set()
                self.wait(lambda:vocabulary.busy)
                self.assertIn('Exported',vocabulary.status.get())
        finally: release.set()


class CredentialRecoveryTests(unittest.TestCase):
    def test_corruption_keeps_bytes_and_application_starts(self):
        for bad in ('{broken', '[]', '{"subdl:api_key": 42}', '{"subdl:api_key":"!!!"}'):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as directory:
                home=Path(directory).resolve(); data=home/'data';data.mkdir()
                path=data/'secrets.json';path.write_text(bad,encoding='utf-8')
                original=path.read_bytes()
                app=Application(home);app.root.withdraw()
                try:
                    self.assertFalse(app.enabled['subdl'].get())
                    self.assertEqual(path.read_bytes(),original)
                    self.assertIn('Unreadable', [v.cget('text') for v in app.secret_indicators.values()])
                finally: app.close()
                self.assertEqual(path.read_bytes(),original)

    def test_dpapi_failure_and_explicit_reset_preserve_original(self):
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory);store=SecretStore(home)
            store.path.write_text('{"subdl:api_key":"YWJj"}',encoding='utf-8')
            original=store.path.read_bytes()
            with patch('subtitledesk.storage.protect',side_effect=OSError('sensitive input')):
                with self.assertRaises(CredentialError) as caught: store.get('subdl','api_key')
                self.assertNotIn('sensitive input',str(caught.exception))
            backup=store.reset()
            self.assertEqual(backup.read_bytes(),original)
            self.assertEqual(store.get('subdl','api_key'),'')

if __name__=='__main__': unittest.main()
