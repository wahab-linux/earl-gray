"""Per-session logs and a separate live Windows debug console."""
from datetime import datetime
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


class DebugLog:
    def __init__(self, directory=None):
        if directory is None:
            directory = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "EarlGray" / "logs"
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        self.path = directory / f"earl-gray-{stamp}-{os.getpid()}.log"
        self.logger = logging.getLogger(f"earlgray.{stamp}")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        self.handler = logging.FileHandler(self.path, encoding="utf-8")
        self.handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s [%(threadName)s] %(message)s", datefmt="%H:%M:%S"))
        self.logger.addHandler(self.handler)
        self.logger.info("Earl Gray started | Python %s | %s", sys.version.split()[0], sys.platform)
        self.closed = False

    def open_terminal(self):
        self.logger.info("Opening live debug terminal: %s", self.path)
        if sys.platform == "win32":
            script = Path(__file__).resolve().parent / "assets" / "show_logs.ps1"
            return subprocess.Popen(["powershell.exe", "-NoLogo", "-NoProfile", "-NoExit", "-ExecutionPolicy", "RemoteSigned", "-File", str(script), "-LogPath", str(self.path)],
                                    creationflags=subprocess.CREATE_NEW_CONSOLE, cwd=self.path.parent)
        if sys.platform == "darwin":
            # Launch a terminal with a generated shell file; filenames stay data.
            import shlex
            script = self.path.with_suffix(".command")
            script.write_text(f"#!/bin/sh\ntail -n 200 -f {shlex.quote(str(self.path))}\n", encoding="utf-8")
            script.chmod(0o700)
            return subprocess.Popen(["open", "-a", "Terminal", str(script)])
        for terminal, flag in (("x-terminal-emulator", "-e"), ("gnome-terminal", "--"), ("xterm", "-e")):
            if program := shutil.which(terminal):
                return subprocess.Popen([program, flag, "tail", "-n", "200", "-F", str(self.path)])
        raise RuntimeError(f"No terminal application found. Open this log file manually: {self.path}")

    def close(self):
        if not self.closed:
            self.logger.info("Earl Gray closed. The session log is retained for debugging.")
            self.logger.removeHandler(self.handler)
            self.handler.close()
            self.closed = True
