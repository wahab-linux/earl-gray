import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from diagnostics import DebugLog


class DebugTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.debug = DebugLog(self.temp.name)
        self.addCleanup(self.debug.close)

    def test_worker_events_and_tracebacks_are_retained(self):
        thread = threading.Thread(target=lambda: self.debug.logger.info("Preparing slides"), name="Conversion")
        thread.start(); thread.join()
        try:
            raise ValueError("broken presentation")
        except ValueError:
            self.debug.logger.exception("Conversion failed")
        self.debug.close()
        content = self.debug.path.read_text(encoding="utf-8")
        self.assertIn("[Conversion] Preparing slides", content)
        self.assertIn("ValueError: broken presentation", content)
        self.assertIn("Earl Gray closed", content)

    def test_windows_terminal_is_a_new_console_with_literal_log_path(self):
        with patch("diagnostics.sys.platform", "win32"), patch("diagnostics.subprocess.CREATE_NEW_CONSOLE", 16, create=True), patch("diagnostics.subprocess.Popen") as launch:
            self.debug.open_terminal()
        args, kwargs = launch.call_args
        self.assertEqual(args[0][0], "powershell.exe")
        self.assertEqual(args[0][-1], str(self.debug.path))
        self.assertEqual(kwargs["creationflags"], 16)
        self.assertNotIn("shell", kwargs)
        self.assertTrue(Path(args[0][args[0].index("-File") + 1]).exists())
