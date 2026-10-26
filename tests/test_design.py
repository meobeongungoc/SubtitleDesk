"""UI contract: secondary appearance controls and usable real ttk widgets."""
from pathlib import Path
import tempfile
import unittest
from subtitledesk.gui import Application

class DesignTests(unittest.TestCase):
    def test_layout_focus_and_scroll(self):
        with tempfile.TemporaryDirectory() as folder:
            app=Application(Path(folder))
            try:
                app.root.geometry('1000x600+20000+20000')
                app.root.withdraw()
                app.root.update()
                self.assertEqual(app.font_picker.winfo_toplevel(),app.root)
                self.assertEqual(app.theme_picker.winfo_toplevel(),app.root)
                app.show_appearance(); app.root.update()
                self.assertEqual(app.pages.select(), str(app.appearance_window))
                app.pages.select(app.main_content)
                buttons=[]
                def walk(w):
                    from tkinter import ttk
                    if isinstance(w,ttk.Button): buttons.append(w)
                    for child in w.winfo_children(): walk(child)
                walk(app.library.btab)
                for button in buttons:
                    self.assertTrue(button.winfo_exists())

                manager=app.theme_manager
                # Native widget commands and keyboard focus survive image styling.
                view=app.library.batch_table
                for i in range(100):view.insert('','end',iid=str(i),values=('',f'Episode {i}','','','','','','Not searched'))
                app.root.update()
                view.yview_moveto(1);app.root.update()
                self.assertTrue(view.exists("99"))
                view.selection_set('99');view.focus('99')
                self.assertEqual(view.focus(),'99')
                for theme in ('blue','warm','green','purple'):
                    manager.apply(theme)
                    self.assertEqual(manager.style.layout('TButton')[0][0],f'Desk.{theme}.regular')
                self.assertEqual(len(manager._surfaces),4)
            finally:app.close()
