"""Verify the packaged Windows app opens and closes from outside the checkout."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def main():
    if sys.platform != "win32":
        raise SystemExit("Run this smoke check on Windows.")
    executable = Path(sys.argv[1]).resolve(strict=True)
    user32 = ctypes.windll.user32
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype = wintypes.BOOL
    with tempfile.TemporaryDirectory(prefix="earl-gray-smoke-") as working:
        process = subprocess.Popen([str(executable)], cwd=working)
        try:
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"Packaged app exited before opening (code {process.returncode}).")
                window = user32.FindWindowW(None, "Earl Gray | A little order, one perfect PDF")
                if window:
                    # Allow initialization to finish before exercising the close protocol.
                    time.sleep(1)
                    if process.poll() is not None:
                        raise RuntimeError("Packaged app exited during initialization.")
                    # Exercise the normal close handler, including temporary-file cleanup.
                    if not user32.PostMessageW(window, 0x0010, 0, 0):
                        raise RuntimeError("Could not close the packaged app window.")
                    if process.wait(timeout=15) != 0:
                        raise RuntimeError(f"Packaged app closed with code {process.returncode}.")
                    print("Packaged Windows app opened and closed successfully.")
                    return
                time.sleep(0.2)
            raise RuntimeError("Packaged app did not open its main window within 45 seconds.")
        finally:
            if process.poll() is None:
                # A failed startup can leave a bootloader child or an error dialog.
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=False)
                process.wait(timeout=10)


if __name__ == "__main__":
    main()
