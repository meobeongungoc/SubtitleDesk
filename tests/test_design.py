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
                app.root.geometry('1000x600')
                app.root.update()
                self.assertFalse(app.appearance_window.winfo_viewable())
                self.assertEqual(app.font_picker.winfo_toplevel(),app.appearance_window)
                self.assertEqual(app.theme_picker.winfo_toplevel(),app.appearance_window)
                app.show_appearance(); app.root.update()
                self.assertTrue(app.appearance_window.winfo_viewable())
                app.appearance_window.withdraw()
                buttons=[]
                def walk(w):
                    from tkinter import ttk
                    if isinstance(w,ttk.Button): buttons.append(w)
                    for child in w.winfo_children(): walk(child)
                walk(app.library.btab)
                for button in buttons:
                    self.assertTrue(button.winfo_viewable())
                    self.assertGreaterEqual(button.winfo_width(), button.winfo_reqwidth())
                manager=app.theme_manager
                # Native widget commands and keyboard focus survive image styling.
                buttons[0].focus_force();app.root.update()
                self.assertEqual(app.root.focus_get(),buttons[0])
                view=app.library.batch_table
                for i in range(100):view.insert('','end',iid=str(i),values=('',f'Episode {i}','','','','','','Not searched'))
                app.root.update()
                view.yview_moveto(1);app.root.update()
                self.assertGreater(view.yview()[0],0)
                view.selection_set('99');view.focus('99')
                self.assertEqual(view.focus(),'99')
                for theme in ('blue','warm','green','purple'):
                    manager.apply(theme)
                    self.assertEqual(manager.style.layout('TButton')[0][0],f'Desk.{theme}.regular')
                self.assertEqual(len(manager._surfaces),4)
            finally:app.close()
