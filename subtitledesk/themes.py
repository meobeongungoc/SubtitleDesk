"""Shared dark palettes and live Tk/ttk styling."""
import ctypes
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
from .surfaces import install_surfaces, mix, icon

THEMES = {
    'blue': ('Modern Neutral · Blue', '#0c151e', '#121d28', '#203041', '#2b5278', '#3478d4'),
    'warm': ('Warm Neutral · Beige', '#12161b', '#1b2026', '#2b2e34', '#655b4e', '#c7a681'),
    'green': ('Green Accent', '#0b191d', '#122328', '#20363b', '#2c6056', '#589d7c'),
    'purple': ('Purple Accent', '#131320', '#1c1b2c', '#2c293e', '#574376', '#875bb6'),
}


class ThemeManager:
    def __init__(self, root):
        self.root = root
        self.style = ttk.Style(root)
        self.style.theme_use('clam')
        self.key = 'blue'
        self._surfaces = {}
        self._icons = {}
        self.font_families = tuple(sorted({name for name in tkfont.families(root)
                                         if not name.startswith('@')}, key=str.casefold))
        self.font_family = 'Segoe UI' if 'Segoe UI' in self.font_families else tkfont.nametofont('TkDefaultFont', root=root).actual('family')
        self.glass_strength = 10
        self.logo = None
        assets = Path(__file__).resolve().parent / 'assets'
        if (assets / 'logo.png').exists():
            self.logo = tk.PhotoImage(master=root, file=str(assets / 'logo.png'))
            root.iconphoto(True, self.logo)
        root.bind_all('<Map>', self._mapped, add='+')

    def icon(self, name):
        if name not in self._icons:
            size = max(14, round(16 * float(self.root.tk.call('tk','scaling')) / (96/72)))
            self._icons[name] = icon(self.root, name, size=size)
        return self._icons[name]

    def _mapped(self, event):
        if isinstance(event.widget, (tk.Tk, tk.Toplevel)):
            self._native(event.widget)

    def _native(self, window):
        window.configure(background=self.colors['bg'])
        window.attributes('-alpha', 1 - self.glass_strength * .0035)
        if self.logo is not None:
            window.iconphoto(False, self.logo)
        if sys.platform == 'win32':
            try:
                get_parent = ctypes.windll.user32.GetParent
                get_parent.argtypes = [ctypes.c_void_p]
                get_parent.restype = ctypes.c_void_p
                hwnd = get_parent(window.winfo_id())
                dark = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), 20,
                    ctypes.byref(dark), ctypes.sizeof(dark))
            except (OSError, ValueError):
                pass

    def set_font(self, family):
        available = {name.casefold(): name for name in self.font_families}
        self.font_family = available.get(str(family).casefold(),
            'Segoe UI' if 'Segoe UI' in self.font_families else self.font_family)
        for name in ('TkDefaultFont','TkTextFont','TkMenuFont','TkHeadingFont','TkCaptionFont',
                     'TkSmallCaptionFont','TkIconFont','TkTooltipFont'):
            try:
                tkfont.nametofont(name, root=self.root).configure(family=self.font_family)
            except tk.TclError:
                pass
        self.apply(self.key)
        return self.font_family

    def set_glass(self, strength):
        self.glass_strength = max(0, min(100, int(round(float(strength) / 5) * 5)))
        for window in [self.root] + [w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)]:
            self._native(window)
        return self.glass_strength

    def apply(self, key):
        self.key = key if key in THEMES else 'blue'
        _, bg, panel, control, selection, accent = THEMES[self.key]
        self.colors = dict(bg=bg, panel=panel, control=control, selection=selection,
                           accent=accent, text='#e8edf3', muted='#adbac9')
        s = self.style
        s.configure('.', font=(self.font_family, 10), background=bg, foreground='#e8edf3',
                    bordercolor=control, lightcolor=control, darkcolor=control,
                    troughcolor=bg, selectbackground=selection, selectforeground='#ffffff')
        s.configure('TFrame', background=bg)
        s.configure('Card.TFrame', background=panel, borderwidth=1, relief='solid')
        s.configure('Card.TLabel', background=panel, foreground='#e8edf3')
        s.configure('TLabel', background=bg)
        s.configure('CardInner.TFrame', background=panel)
        s.configure('CardHint.TLabel', background=panel, foreground='#adbac9')
        s.configure('CardTitle.TLabel', background=panel, font=(self.font_family,10,'bold'))
        s.configure('Title.TLabel', font=(self.font_family, 19, 'bold'))
        s.configure('Hint.TLabel', foreground='#adbac9')
        s.configure('TButton', background=control, padding=(10, 4), width=0, borderwidth=0, relief='flat')
        s.map('TButton', background=[('disabled',panel), ('pressed',selection), ('active',selection)],
              foreground=[('disabled','#7c8894')])
        accent_text = '#141c22' if self.key in ('warm','green') else '#ffffff'
        s.configure('Accent.TButton', background=accent, foreground=accent_text)
        s.map('Accent.TButton', background=[('disabled',control), ('pressed',selection), ('active',accent)],
              foreground=[('disabled','#7c8894'), ('pressed','#ffffff'), ('!disabled',accent_text)])
        for name in ('TEntry', 'TCombobox', 'TSpinbox'):
            s.configure(name, fieldbackground=panel, background=control, foreground='#e8edf3',
                        insertcolor='#e8edf3', arrowcolor='#e8edf3', padding=5)
            s.map(name, fieldbackground=[('disabled',bg), ('readonly',panel)],
                  foreground=[('disabled','#7c8894'), ('readonly','#e8edf3')],
                  selectbackground=[('!disabled',selection)], selectforeground=[('!disabled','#ffffff')])
        for name in ('TCheckbutton','TRadiobutton'):
            s.configure(name, background=bg, indicatorbackground=panel, indicatorforeground=accent)
            s.map(name, background=[('active',bg)], foreground=[('disabled','#7c8894')],
                  indicatorbackground=[('selected',accent), ('!selected',panel)])
        s.configure('Treeview', background=panel, fieldbackground=panel, rowheight=29,
                    foreground='#e8edf3', borderwidth=0)
        s.map('Treeview', background=[('selected',selection)], foreground=[('selected','#ffffff')])
        s.configure('Treeview.Heading', background=panel, foreground='#adbac9', padding=(5,5),
                    font=(self.font_family,9))
        s.map('Treeview.Heading', background=[('active',selection)])
        s.configure('TNotebook', background=bg, borderwidth=0)
        s.configure('TNotebook.Tab', background=control, padding=(12,7))
        s.map('TNotebook.Tab', background=[('selected',selection), ('active',panel)])
        s.configure('TLabelframe', background=bg)
        s.configure('TLabelframe.Label', background=bg, foreground='#adbac9')
        s.configure('TPanedwindow', background=bg)
        for orient in ('Vertical','Horizontal'):
            s.configure(orient+'.TScrollbar', background=control, arrowcolor='#adbac9', troughcolor=panel)
        for option, value in [('background',panel), ('foreground','#e8edf3'),
                              ('selectBackground',selection), ('selectForeground','#ffffff')]:
            self.root.option_add('*TCombobox*Listbox.'+option, value)
        self.root.option_add('*Background',bg)
        install_surfaces(self)
        self._walk(self.root)
        return self.key

    def _walk(self, widget):
        c = self.colors
        ancestor = getattr(widget, 'master', None)
        in_card = False
        while ancestor is not None:
            if isinstance(ancestor, ttk.Frame) and ancestor.cget('style') == 'Card.TFrame':
                in_card = True
                break
            ancestor = getattr(ancestor, 'master', None)
        if in_card and isinstance(widget, ttk.Frame) and not widget.cget('style'):
            widget.configure(style='CardInner.TFrame')
        if in_card and isinstance(widget, ttk.Label):
            if widget.cget('style') == 'Hint.TLabel':
                widget.configure(style='CardHint.TLabel')
            elif not widget.cget('style'):
                widget.configure(style='Card.TLabel')
        if 'font' in widget.keys() and widget.cget('font'):
            actual = tkfont.Font(root=self.root, font=widget.cget('font')).actual()
            widget.configure(font=(self.font_family, actual['size'], actual['weight'], actual['slant']))
        if isinstance(widget, (tk.Tk,tk.Toplevel)):
            self._native(widget)
        elif isinstance(widget, tk.Text):
            widget.configure(background=c['panel'], foreground=c['text'], insertbackground=c['text'],
                             selectbackground=c['selection'], selectforeground='#ffffff',
                             highlightbackground=c['control'], highlightcolor=c['accent'])
        elif isinstance(widget, tk.Frame) and not isinstance(widget, ttk.Frame):
            widget.configure(background=c['bg'])
        elif isinstance(widget, tk.Scrollbar) and not isinstance(widget, ttk.Scrollbar):
            widget.configure(background=c['control'], troughcolor=c['panel'],
                             activebackground=c['selection'])
        elif isinstance(widget, tk.Scale):
            widget.configure(background=c['bg'], troughcolor=c['panel'], foreground=c['text'],
                             activebackground=c['accent'])
        if isinstance(widget, ttk.Combobox):
            popdown = widget.tk.call('ttk::combobox::PopdownWindow', str(widget))
            listing = str(popdown) + '.f.l'
            if widget.tk.call('winfo', 'exists', listing):
                widget.tk.call(listing, 'configure', '-background', c['panel'],
                    '-foreground', c['text'], '-selectbackground', c['selection'],
                    '-selectforeground', '#ffffff', '-font', (self.font_family,10))
        if isinstance(widget, ttk.Treeview):
            widget.tag_configure('exact', background=c['selection'], foreground='#ffffff')
            widget.tag_configure('saved', background='#183e32', foreground='#9ce6b5')
        for child in widget.winfo_children():
            self._walk(child)
