"""Capture real Tk windows using isolated, explicitly labelled synthetic data."""
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import sys
import tempfile
import os
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from subtitledesk.gui import Application
from subtitledesk.batch import Episode, identify
from subtitledesk.providers import Result
from subtitledesk.surfaces import png


def capture(window, path):
    window.update()
    u,g=C.windll.user32,C.windll.gdi32
    u.GetParent.restype=W.HWND
    hwnd=u.GetParent(window.winfo_id())
    rect=W.RECT();u.GetWindowRect(hwnd,C.byref(rect))
    w,h=rect.right-rect.left,rect.bottom-rect.top
    u.GetWindowDC.restype=W.HDC
    g.CreateCompatibleDC.restype=W.HDC
    g.CreateCompatibleDC.argtypes=[W.HDC]
    g.CreateCompatibleBitmap.restype=W.HBITMAP
    g.CreateCompatibleBitmap.argtypes=[W.HDC,C.c_int,C.c_int]
    g.SelectObject.restype=W.HGDIOBJ
    g.SelectObject.argtypes=[W.HDC,W.HGDIOBJ]
    g.DeleteDC.argtypes=[W.HDC];g.DeleteObject.argtypes=[W.HGDIOBJ]
    u.ReleaseDC.argtypes=[W.HWND,W.HDC]
    u.PrintWindow.argtypes=[W.HWND,W.HDC,W.UINT]
    g.GetDIBits.argtypes=[W.HDC,W.HBITMAP,W.UINT,W.UINT,C.c_void_p,C.c_void_p,W.UINT]
    dc=u.GetWindowDC(hwnd); mem=g.CreateCompatibleDC(dc)
    bitmap=g.CreateCompatibleBitmap(dc,w,h); old=g.SelectObject(mem,bitmap)
    try:
        if not u.PrintWindow(hwnd,mem,2): raise RuntimeError('PrintWindow failed')
        header=__import__('struct').pack('<IiiHHIIiiII',40,w,-h,1,32,0,w*h*4,0,0,0,0)
        info=C.create_string_buffer(header)
        pixels=C.create_string_buffer(w*h*4)
        g.SelectObject(mem,old)
        if g.GetDIBits(mem,bitmap,0,h,pixels,info,0)!=h: raise RuntimeError('GetDIBits failed')
        rgba=bytearray(pixels.raw)
        rgba[0::4],rgba[2::4]=pixels.raw[2::4],pixels.raw[0::4]
        rgba[3::4]=b'\xff'*(w*h)
        path.write_bytes(png(w,h,rgba))
    finally:
        g.DeleteObject(bitmap);g.DeleteDC(mem);u.ReleaseDC(hwnd,dc)


def main():
    output=Path(__file__).resolve().parents[1]/'test-artifacts'/'design'
    output.mkdir(exist_ok=True)
    scale = float(os.environ.get('DESIGN_SCALE','1'))
    if scale != 1:
        from subtitledesk.themes import ThemeManager
        original = ThemeManager.__init__
        def scaled(self, root):
            root.tk.call('tk','scaling',(96/72)*scale)
            original(self,root)
        ThemeManager.__init__=scaled
        output=output/f'scale-{scale}'
        output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        app=Application(Path(folder))
        app.root.title('SubtitleDesk 0.5.0 — DESIGN CHECK / SAMPLE DATA')
        app.root.geometry('1280x760+30+30')
        app.theme_manager.set_glass(0)
        rows=[]
        for i in range(1,21):
            path=Path(folder)/'Example Series'/f'Example.Series.S01E{i:02d}.1080p.BluRay.x264-GROUP.mkv'
            candidates=[]
            for provider,lang in [('subdl','en'),('opensubtitles','vi')]:
                for j in range(8):
                    name=path.with_suffix('.srt').name if j==0 else f'Example.Series.S01E{i:02d}.WEB-DL.Release.{j}.srt'
                    candidates.append((100-j,Result(provider,str(j),'Example Series',lang,filename=name)))
            rows.append(Episode(path,identify(path),state='Not searched',candidates=candidates))
        app.library.set_rows(rows)
        app.library.movie_choice.set('Example Series (sample)')
        app.library.folder_label.set('20 movie files · Example Series / Season 01 · sample data')
        app.library.bstatus.set('Design check — synthetic data only. No search or downloads were performed.')
        app.library.notice.set('Exact filename matches are highlighted. Existing subtitles are preserved.')
        app.library.show_candidates()
        app.root.update()
        # Equal cards after actual geometry is available.
        width=app.library.panes.winfo_width()
        app.library.panes.sashpos(0,width//3)
        app.library.panes.sashpos(1,width*2//3)
        for key in ('blue','warm','green','purple'):
            app.theme_manager.apply(key)
            app.theme_label.set(__import__('subtitledesk.themes',fromlist=['THEMES']).THEMES[key][0])
            capture(app.root,output/f'{key}.png')
        app.show_appearance()
        app.appearance_window.geometry('+60+60')
        capture(app.appearance_window,output/'appearance.png')
        app.appearance_window.withdraw()
        app.root.geometry('1000x600+30+30');app.root.update()
        width=app.library.panes.winfo_width()
        app.library.panes.sashpos(0,width//3);app.library.panes.sashpos(1,width*2//3)
        capture(app.root,output/'compact.png')
        app.close()
    print(output)

if __name__=='__main__': main()
