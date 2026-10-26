"""Background vocabulary scans with a preview and explicit Anki export."""
import gc
import copy
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .vocabulary import Cancelled, extract_folder, export_anki, recycle_scanned_subtitles
from .storage import dialog_directory


class VocabularyWindow:
    def __init__(self, app, folder=''):
        self.app = app
        self.window = ttk.Frame(app.vocabulary_page)
        self.window.pack(fill="both", expand=True)
        self.window.bind('<Destroy>', self.destroyed, add='+')
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.report = None
        self.busy = False
        self.closed = False
        self.folder = tk.StringVar(master=self.window, value=dialog_directory(
            folder, app.settings.get('vocabulary_input_dir'), app.settings.get('library_root')) or '')
        self.levels = tk.StringVar(master=self.window, value='C1 + C2')
        self.status = tk.StringVar(master=self.window, value='Choose the movie folder, then scan its English subtitles.')
        body = ttk.Frame(self.window, padding=16)
        body.pack(fill='both', expand=True)
        row = ttk.Frame(body)
        row.pack(fill='x', pady=(0, 10))
        ttk.Label(row, text='Movie folder').pack(side='left', padx=(0, 8))
        self.folder_entry = ttk.Entry(row, textvariable=self.folder)
        self.folder_entry.pack(side='left', fill='x', expand=True)
        self.browse_button = ttk.Button(row, text='Browse…', command=self.browse)
        self.browse_button.pack(side='left', padx=(8, 0))
        controls = ttk.Frame(body)
        controls.pack(fill='x')
        ttk.Label(controls, text='Levels').pack(side='left', padx=(0, 8))
        self.level_picker = ttk.Combobox(controls, textvariable=self.levels, values=('C1 + C2', 'C1', 'C2'),
                                         state='readonly', width=12)
        self.level_picker.pack(side='left')
        self.scan_button = ttk.Button(controls, text='Scan subtitles', style='Accent.TButton', command=self.scan)
        self.scan_button.pack(side='left', padx=8)
        self.cancel_button = ttk.Button(controls, text='Cancel', command=self.cancel_scan, state='disabled')
        self.cancel_button.pack(side='left')
        self.export_button = ttk.Button(controls, text='Export Anki TXT…', command=self.export, state='disabled')
        self.export_button.pack(side='right')
        self.progress = ttk.Progressbar(body, mode='determinate')
        self.progress.pack(fill='x', pady=10)
        ttk.Label(body, text='English SRT / VTT / ASS / SSA files, including subfolders. Embedded tracks are not read.',
                  style='Hint.TLabel', wraplength=850).pack(anchor='w')
        ttk.Label(body, text='After a successful export, subtitle files found in this folder during the scan move to the Windows Recycle Bin. Changed files stay in place.',
                  style='Hint.TLabel', wraplength=850).pack(anchor='w', pady=(4, 0))
        ttk.Label(body, text='List-based CEFR estimates; lower-level homographs and unknown words are excluded. '
                  'Cards contain examples, not dictionary definitions.', style='Hint.TLabel', wraplength=850).pack(anchor='w', pady=(4, 8))
        table_frame = ttk.Frame(body)
        table_frame.pack(fill='both', expand=True)
        self.table = ttk.Treeview(table_frame, columns=('word', 'level', 'count', 'example'), show='headings')
        for key, title, width in [('word', 'Word / phrase', 150), ('level', 'CEFR', 55),
                                  ('count', 'Occurrences', 85), ('example', 'Subtitle example', 420)]:
            self.table.heading(key, text=title)
            self.table.column(key, width=width, minwidth=45, stretch=key in {'word', 'example'})
        scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        bottom = ttk.Frame(body)
        bottom.pack(fill='x', pady=(10, 0))
        ttk.Label(bottom, textvariable=self.status, wraplength=700).pack(side='left', fill='x', expand=True)
        self.details_button = ttk.Button(bottom, text='Scan details', command=self.details, state='disabled')
        self.details_button.pack(side='right')
        self.details_text = tk.Text(body, height=5, wrap='word')
        self.folder.trace_add('write', self.invalidate)
        self.levels.trace_add('write', self.invalidate)
        app.theme_manager.apply(app.theme_key)
        self.timer = self.app.root.after(100, self.poll)

    def invalidate(self, *args):
        if not self.busy and self.report is not None:
            self.report = None
            self.table.delete(*self.table.get_children())
            self.export_button.configure(state='disabled')
            self.details_button.configure(state='disabled')
            self.status.set('Folder or levels changed. Scan again to refresh the preview.')

    def browse(self):
        folder = filedialog.askdirectory(parent=self.window, title='Choose movie folder', initialdir=dialog_directory(
            self.app.settings.get('vocabulary_input_dir'), self.folder.get(), self.app.settings.get('library_root')))
        if folder:
            self.folder.set(folder)
            self.remember_directory('vocabulary_input_dir', folder)

    def remember_directory(self, key, folder):
        if Path(folder).is_dir():
            self.app.settings[key] = str(Path(folder).resolve())
            self.app.persist(False)

    def scan(self):
        if self.busy:
            return
        folder = self.folder.get().strip()
        if not folder or not Path(folder).is_dir():
            self.status.set('Choose an existing movie folder.')
            return
        self.remember_directory('vocabulary_input_dir', folder)
        self.cancel.clear()
        self.busy = True
        self.report = None
        self.table.delete(*self.table.get_children())
        self.export_button.configure(state='disabled')
        self.details_button.configure(state='disabled')
        for control in (self.scan_button, self.browse_button, self.folder_entry, self.level_picker):
            control.configure(state='disabled')
        self.cancel_button.configure(state='normal')
        self.status.set('Scanning English subtitles…')
        self.progress.configure(value=0, maximum=1)
        levels = ('C1', 'C2') if self.levels.get() == 'C1 + C2' else (self.levels.get(),)
        def worker():
            try:
                report = extract_folder(folder, levels=levels, cancel=self.cancel,
                    progress=lambda current, total, name: self.events.put(('progress', current, total, name)))
                self.events.put(('done', report))
            except Cancelled as exc:
                self.events.put(('error', str(exc)))
            except (OSError, ValueError) as exc:
                self.events.put(('error', str(exc)))
            except Exception:
                # Keep unrelated paths/credentials out of UI errors and logs.
                self.events.put(('error', 'Could not scan this folder. Check file access and the bundled vocabulary data.'))
        # Finalize closed Tk widgets on the UI thread before the lexicon allocates heavily.
        gc.collect()
        threading.Thread(target=worker, daemon=True).start()

    def cancel_scan(self):
        if self.busy:
            self.cancel.set()
            self.status.set('Cancelling…')

    def poll(self):
        if self.closed:
            return
        for _ in range(100):
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if event[0] == 'cleanup_progress':
                self.progress.configure(value=event[1], maximum=max(1, event[2]))
                self.status.set(f'Saved export. Recycling subtitles: {event[1]}/{event[2]}')
                continue
            if event[0] == 'export_done':
                self.finish_export(event)
                continue
            if event[0] == 'progress':
                self.progress.configure(value=event[1], maximum=max(1, event[2]))
                self.status.set(f'{event[1]}/{event[2]} · {event[3]}')
                continue
            self.busy = False
            for control in (self.scan_button, self.browse_button, self.folder_entry):
                control.configure(state='normal')
            self.level_picker.configure(state='readonly')
            self.cancel_button.configure(state='disabled')
            if event[0] == 'error':
                self.status.set(event[1])
            elif self.cancel.is_set():
                self.status.set('Scan cancelled; no export was written.')
            else:
                self.report = event[1]
                for i, card in enumerate(self.report.cards):
                    self.table.insert('', 'end', iid=str(i), values=(card.term, card.level, card.count, card.examples[0][0]))
                self.export_button.configure(state='normal' if self.report.cards else 'disabled')
                self.details_button.configure(state='normal')
                self.status.set(f'{len(self.report.cards)} unique words/phrases · {self.report.read}/{self.report.found} subtitles read · '
                                f'{self.report.duplicates} duplicate copies · {len(self.report.skipped)} skipped.' +
                                (' No matches: add English subtitle files or check Scan details.' if not self.report.cards else ''))
        self.timer = self.app.root.after(100, self.poll)

    def export(self):
        if not self.report or self.busy:
            return
        path = filedialog.asksaveasfilename(parent=self.window, title='Export vocabulary for Anki',
            initialdir=dialog_directory(self.app.settings.get('vocabulary_export_dir'), self.report.root),
            initialfile=self.report.root.name + '-C1-C2-Anki.txt', defaultextension='.txt',
            filetypes=[('Anki text file', '*.txt')], confirmoverwrite=False)
        if not path:
            return
        self.remember_directory('vocabulary_export_dir', Path(path).parent)
        report = copy.deepcopy(self.report)
        self.busy = True
        self.cancel.clear()
        for control in (self.scan_button, self.browse_button, self.folder_entry, self.level_picker,
                        self.export_button, self.details_button):
            control.configure(state='disabled')
        self.cancel_button.configure(state='normal')
        self.status.set('Saving Anki TXT…')
        def worker():
            try:
                export_anki(report, path)
            except FileExistsError:
                self.events.put(('export_done', None, 0, [], 'That file already exists. Choose a new export filename.'))
            except Exception:
                self.events.put(('export_done', None, 0, [], 'Could not save export. No subtitles were recycled. Check file access and try another filename.'))
            else:
                try:
                    moved, kept = recycle_scanned_subtitles(report, cancel=self.cancel,
                        progress=lambda current, total: self.events.put(('cleanup_progress', current, total)))
                    self.events.put(('export_done', path, moved, kept, ''))
                except Exception:
                    self.events.put(('export_done', path, 0, [], 'Export saved; subtitle cleanup could not finish. Remaining files were kept.'))
        threading.Thread(target=worker, daemon=True).start()

    def finish_export(self, event):
        _, path, moved, kept, error = event
        self.busy = False
        for control in (self.scan_button, self.browse_button, self.folder_entry):
            control.configure(state='normal')
        self.level_picker.configure(state='readonly')
        self.cancel_button.configure(state='disabled')
        self.export_button.configure(state='normal' if self.report and self.report.cards else 'disabled')
        self.details_button.configure(state='normal' if self.report else 'disabled')
        if error:
            self.status.set(error)
        else:
            self.status.set(f'Exported {len(self.report.cards)} cards to {path}. Moved {moved} subtitle(s) to the Recycle Bin; kept {len(kept)} file(s).')
        if kept:
            self.set_details('\n'.join(f'{name}: {reason}' for name, reason in kept))

    def set_details(self, text):
        self.details_text.configure(state='normal')
        self.details_text.delete('1.0', 'end')
        self.details_text.insert('1.0', text)
        self.details_text.configure(state='disabled')
        self.details_text.pack(fill='x', pady=(8, 0))

    def details(self):
        if self.report:
            reasons = '\n'.join(f'{path}: {reason}' for path, reason in self.report.skipped) or 'No files were skipped.'
            self.set_details(f'Folder: {self.report.root}\nDuplicate copies skipped: {self.report.duplicates}\n\n{reasons}')

    def stop(self):
        if self.closed:
            return
        self.closed = True
        self.cancel.set()
        self.app.root.after_cancel(self.timer)

    def destroyed(self, event):
        if event.widget is self.window:
            self.stop()

    def close(self):
        self.app.pages.select(self.app.main_content)
