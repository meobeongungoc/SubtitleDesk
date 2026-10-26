"""Run disposable Tk application tests with UI-thread garbage collection."""
import gc
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))


class UIThreadResult(unittest.TextTestResult):
    def startTest(self, test):
        # Several disposable Tk roots share this test process. Never finalize their
        # variable/image cycles on a provider or vocabulary worker thread.
        gc.collect()
        super().startTest(test)


if __name__ == '__main__':
    gc.disable()
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), 'test_*.py')
    result = unittest.TextTestRunner(verbosity=2, resultclass=UIThreadResult).run(suite)
    gc.collect()
    raise SystemExit(not result.wasSuccessful())
