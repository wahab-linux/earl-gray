"""Bounded ZIP import into app-owned temporary storage."""
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile

MAX_PDFS = 2000
MAX_PDF_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024


@dataclass(frozen=True)
class ImportedPdf:
    path: Path
    name: str
    source: str
    archive: Path


class ArchiveStore:
    def __init__(self):
        self._temporary = tempfile.TemporaryDirectory(prefix="earl-gray-")
        self.root = Path(self._temporary.name)

    def extract(self, archive):
        """Import PDF members only; archive paths are never used as output paths."""
        archive = Path(archive).resolve()
        folder = Path(tempfile.mkdtemp(prefix="zip-", dir=self.root))
        try:
            with zipfile.ZipFile(archive) as source:
                members = [entry for entry in source.infolist() if not entry.is_dir() and entry.filename.lower().endswith(".pdf")]
                if len(members) > MAX_PDFS:
                    raise ValueError(f"This ZIP contains too many PDFs (maximum {MAX_PDFS}).")
                total = 0
                for entry in members:
                    relative = PurePosixPath(entry.filename.replace("\\", "/"))
                    if relative.is_absolute() or ".." in relative.parts or any(":" in part for part in relative.parts):
                        raise ValueError("This ZIP contains an unsafe PDF path.")
                    if stat.S_ISLNK(entry.external_attr >> 16):
                        raise ValueError("PDF links inside ZIP files are not supported.")
                    if entry.flag_bits & 1:
                        raise ValueError("Unlock this password-protected ZIP before adding it.")
                    if entry.file_size > MAX_PDF_BYTES:
                        raise ValueError("A PDF in this ZIP exceeds the 256 MB import limit.")
                    total += entry.file_size
                if total > MAX_TOTAL_BYTES:
                    raise ValueError("The PDFs in this ZIP exceed the 512 MB import limit.")
                imported = []
                actual_total = 0
                for index, entry in enumerate(members):
                    relative = PurePosixPath(entry.filename.replace("\\", "/"))
                    # Generated names also avoid Windows reserved names and duplicate basenames.
                    destination = folder / f"{index:05d}.pdf"
                    written = 0
                    with source.open(entry) as incoming, destination.open("wb") as outgoing:
                        while chunk := incoming.read(1024 * 1024):
                            written += len(chunk)
                            actual_total += len(chunk)
                            if written > MAX_PDF_BYTES or actual_total > MAX_TOTAL_BYTES:
                                raise ValueError("This ZIP exceeds the PDF import size limits.")
                            outgoing.write(chunk)
                    parent = "" if str(relative.parent) == "." else f" / {relative.parent}"
                    imported.append(ImportedPdf(destination, relative.name, f"{archive.name}{parent}", archive))
            return imported
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise

    def close(self):
        self._temporary.cleanup()
