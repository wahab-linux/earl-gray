"""PDF inspection and selection order, independent of the desktop interface."""
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image
import pypdfium2 as pdfium
from pypdf import PdfReader


@dataclass(eq=False)
class PdfItem:
    path: Path
    display_name: str = ""
    origin: str = ""
    archive: Path | None = None
    size: int = 0
    pages: int = 0
    preview: Image.Image | None = None
    ready: bool = False
    error: str = ""

    @property
    def name(self):
        return self.display_name or self.path.name


def inspect_pdf(path):
    """Read metadata and a bounded first-page preview; call on one worker thread."""
    path = Path(path)
    size = path.stat().st_size
    # Match the merger's password policy and detect unreadable page trees early.
    with path.open("rb") as source:
        reader = PdfReader(source)
        if reader.is_encrypted:
            raise ValueError("Password protected: unlock this PDF first.")
        pages = len(reader.pages)
    if not pages:
        raise ValueError("This PDF has no pages.")
    with pdfium.PdfDocument(path) as document:
        page = document[0]
        try:
            width, height = page.get_size()
            scale = min(144 / max(width, 1), 168 / max(height, 1))
            bitmap = page.render(scale=scale)
            try:
                preview = bitmap.to_pil().convert("RGB").copy()
            finally:
                bitmap.close()
        finally:
            page.close()
    return size, pages, preview


def format_size(size):
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


@dataclass
class Library:
    items: list[PdfItem] = field(default_factory=list)
    chosen: list[PdfItem] = field(default_factory=list)

    def add(self, paths):
        existing = {item.path for item in self.items}
        added = []
        for path in paths:
            path = Path(path).resolve()
            if path.suffix.lower() == ".pdf" and path not in existing:
                item = PdfItem(path)
                self.items.append(item)
                added.append(item)
                existing.add(path)
        return added

    def toggle(self, item):
        if item in self.chosen:
            self.chosen.remove(item)
        elif item in self.items and item.ready and not item.error:
            self.chosen.append(item)

    def select_all(self):
        for item in self.items:
            if item.ready and not item.error and item not in self.chosen:
                self.chosen.append(item)

    def move(self, item, delta):
        if item not in self.chosen:
            return
        index = self.chosen.index(item)
        target = index + delta
        if 0 <= target < len(self.chosen):
            self.chosen[index], self.chosen[target] = self.chosen[target], self.chosen[index]

    def drop(self, item, target):
        if item is target or item not in self.chosen or target not in self.chosen:
            return
        index = self.chosen.index(target)
        self.chosen.remove(item)
        self.chosen.insert(index, item)

    def remove(self, item):
        if item in self.chosen:
            self.chosen.remove(item)
        if item in self.items:
            self.items.remove(item)

    def merge_paths(self):
        return [item.path for item in self.chosen]
