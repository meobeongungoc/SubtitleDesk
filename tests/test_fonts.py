import json
from pathlib import Path
import tempfile
import unittest
from tkinter import font as tkfont
from subtitledesk.gui import Application


class FontTests(unittest.TestCase):
    def test_installed_filter_apply_and_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            app = Application(home)
            app.root.withdraw()
            chosen = next((f for f in app.theme_manager.font_families if f == 'Arial'),
                          app.theme_manager.font_families[0])
            try:
                self.assertIn(chosen, tkfont.families(app.root))
                app.font_choice.set(chosen[:3])
                app.filter_fonts()
                self.assertIn(chosen, app.font_picker.cget('values'))
                app.font_choice.set(chosen)
                app.change_font()
                self.assertEqual(app.theme_manager.font_family,chosen)
                self.assertEqual(tkfont.Font(root=app.root,font=app.preview.cget('font')).actual('family'),chosen)
                app.theme_manager.apply('green')
                self.assertEqual(tkfont.Font(root=app.root,
                    font=app.theme_manager.style.lookup('.', 'font')).actual('family'),chosen)
                self.assertEqual(json.loads((home/'data/settings.json').read_text())['font_family'],chosen)
            finally:
                app.close()
            app = Application(home)
            app.root.withdraw()
            try:
                self.assertEqual(app.theme_manager.font_family,chosen)
                app.font_choice.set('Nonexistent Font 908172')
                app.change_font()
                self.assertEqual(app.settings['font_family'],chosen)
                app.theme_manager.set_font('Nonexistent Font 908172')
                self.assertIn(app.theme_manager.font_family,app.theme_manager.font_families)
            finally:
                app.close()
