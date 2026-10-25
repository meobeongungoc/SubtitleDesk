"""Live switching and persistence using an isolated data folder."""
import json
import tempfile
import unittest
from pathlib import Path
from subtitledesk.gui import Application
from subtitledesk.themes import THEMES


class ThemeTests(unittest.TestCase):
    def test_live_switch_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            app = Application(home)
            app.root.withdraw()
            try:
                self.assertIsNotNone(app.theme_manager.logo)
                for key, palette in THEMES.items():
                    app.theme_label.set(palette[0])
                    app.change_theme()
                    app.root.update_idletasks()
                    self.assertEqual(app.root.cget('background'), palette[1])
                    self.assertEqual(app.preview.cget('background'), palette[2])
                    self.assertEqual(app.tools_window.cget('background'), palette[1])
                    self.assertEqual(json.loads((home/'data/settings.json').read_text())['theme'], key)
                    view = app.library.source_views['subdl']
                    self.assertEqual(view.tag_configure('exact')['background'], palette[4])
                    self.assertEqual(view.tag_configure('saved')['background'], '#183e32')
                    pop = app.root.tk.call('ttk::combobox::PopdownWindow', str(app.theme_picker))
                    self.assertEqual(app.root.tk.call(str(pop)+'.f.l', 'cget','-background'),palette[2])
                self.assertEqual(float(app.glass_scale.cget('resolution')), 5)
                for strength in range(0, 101, 5):
                    app.change_glass(str(strength))
                    self.assertEqual(app.theme_manager.glass_strength, strength)
                    self.assertEqual(app.settings['glass_strength'], strength)
                app.change_glass('35')
                app.save_glass()
                self.assertEqual(json.loads((home/'data/settings.json').read_text())['glass_strength'],35)
            finally:
                app.close()
            resumed = Application(home)
            resumed.root.withdraw()
            try:
                self.assertEqual(resumed.theme_key, 'purple')
                self.assertEqual(resumed.theme_manager.glass_strength, 35)
                self.assertEqual(resumed.theme_manager.apply('missing-theme'), 'blue')
            finally:
                resumed.close()
