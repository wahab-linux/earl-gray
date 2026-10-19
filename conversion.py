"""Local PPTX rendering with LibreOffice or installed Microsoft PowerPoint."""
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from library import inspect_pdf


def find_libreoffice():
    for name in ("soffice", "libreoffice"):
        if executable := shutil.which(name):
            console = Path(executable).with_suffix(".com")
            return str(console) if sys.platform == "win32" and console.is_file() else executable
    candidates = [Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")]
    if sys.platform == "win32":
        for variable in ("ProgramFiles", "ProgramFiles(x86)"):
            if folder := os.environ.get(variable):
                candidates.extend(Path(folder) / "LibreOffice/program" / name for name in ("soffice.com", "soffice.exe"))
    return next((str(path) for path in candidates if path.is_file()), None)


def powerpoint_available():
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"PowerPoint.Application\CLSID"):
            return True
    except OSError:
        return False


class SlideConverter:
    def __init__(self, root, logger=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.logger = logger or logging.getLogger("earlgray")

    def prepare(self, source, progress=None):
        source = Path(source)
        pdf = self.convert(source, progress=progress) if source.suffix.lower() == ".pptx" else source
        _, pages, preview = inspect_pdf(pdf, progress=progress)
        return pdf, source.stat().st_size, pages, preview

    def convert(self, source, progress=None):
        source = Path(source).resolve()
        work = Path(tempfile.mkdtemp(prefix="deck-", dir=self.root))
        target = work / f"{source.stem}.pdf"
        try:
            if office := find_libreoffice():
                profile = (work / "profile").as_uri()
                command = [office, f"-env:UserInstallation={profile}", "--headless", "--convert-to", "pdf:impress_pdf_Export", "--outdir", str(work), str(source)]
                renderer = "LibreOffice"
            elif powerpoint_available():
                script = Path(__file__).resolve().parent / "assets" / "convert_powerpoint.ps1"
                command = ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "RemoteSigned", "-File", str(script), "-SourceFile", str(source), "-OutputFile", str(target)]
                renderer = "Microsoft PowerPoint"
            else:
                raise RuntimeError("To import PPTX, install LibreOffice (free) or Microsoft PowerPoint on Windows, then try again. PDFs work without either app.")
            if progress:
                progress("Converting PowerPoint slides", f"Rendering slides with {renderer}; large decks can take longer")
            self.logger.info("Converting slides with %s: %s", renderer, source)
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), cwd=work)
            if result.stdout.strip():
                self.logger.info("%s: %s", renderer, result.stdout.strip())
            if result.stderr.strip():
                self.logger.warning("%s: %s", renderer, result.stderr.strip())
            if result.returncode or not target.is_file() or not target.stat().st_size:
                raise RuntimeError(f"{renderer} could not convert {source.name}. Open the presentation in that app to check it, or open the debug terminal for details.")
            self.logger.info("Slide conversion complete: %s", source.name)
            return target
        except subprocess.TimeoutExpired as error:
            shutil.rmtree(work, ignore_errors=True)
            raise RuntimeError(f"Slide conversion timed out for {source.name}. Close any conversion dialog and try again.") from error
        except Exception:
            shutil.rmtree(work, ignore_errors=True)
            raise
