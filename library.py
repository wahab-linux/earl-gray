"""PDF inspection and selection order, independent of the desktop interface."""
from dataclasses import dataclass, field
from pathlib import Path
import re
import unicodedata

from PIL import Image
import pypdfium2 as pdfium
from pypdf import PdfReader


@dataclass(eq=False)
class PdfItem:
    path: Path
    pdf_path: Path | None = None
    display_name: str = ""
    origin: str = ""
    archive: Path | None = None
    size: int = 0
    pages: int = 0
    modified_ns: int | None = None
    preview: Image.Image | None = None
    ready: bool = False
    error: str = ""

    @property
    def name(self):
        return self.display_name or self.path.name


def inspect_pdf(path, progress=None):
    """Read metadata and a bounded first-page preview; call on one worker thread."""
    path = Path(path)
    size = path.stat().st_size
    if progress:
        progress("Reading PDF", "Checking encryption and counting pages")
    # Match the merger's password policy and detect unreadable page trees early.
    with path.open("rb") as source:
        reader = PdfReader(source)
        if reader.is_encrypted:
            raise ValueError("Password protected: unlock this PDF first.")
        pages = len(reader.pages)
    if not pages:
        raise ValueError("This PDF has no pages.")
    if progress:
        progress("Rendering thumbnail", f"{pages} page(s) found; rendering the first page")
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


def natural_name(name):
    """Compare original filenames case-insensitively, with numeric runs as numbers."""
    name = unicodedata.normalize("NFKC", name).strip().casefold()
    return tuple((1, int(part)) if part.isdecimal() else (0, part)
                 for part in re.split(r"([0-9]+)", name))


@dataclass
class Library:
    items: list[PdfItem] = field(default_factory=list)
    chosen: list[PdfItem] = field(default_factory=list)

    def add(self, paths):
        existing = {item.path for item in self.items}
        added = []
        for path in paths:
            path = Path(path).resolve()
            if path.suffix.lower() in (".pdf", ".pptx") and path not in existing:
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
        self.chosen[:] = [item for item in self.items if item.ready and not item.error]

    def sort(self, by="Name", descending=False, reorder_chosen=True):
        """Sort cached source metadata; missing values stay last in either direction.

        An explicit sort also renumbers picked files. Import can sort the browser
        without disturbing an existing manually arranged merge queue.
        """
        attributes = {"Size": "size", "Date modified": "modified_ns", "Pages": "pages"}
        if by != "Name" and by not in attributes:
            raise ValueError(f"Unknown sort field: {by}")
        ordered = sorted(self.items, key=lambda item: (natural_name(item.name),
                         item.name.casefold(), str(item.path).casefold()))
        if by == "Name":
            if descending:
                ordered.reverse()
        else:
            attribute = attributes[by]
            known, unknown = [], []
            for item in ordered:
                value = getattr(item, attribute)
                (known if value is not None and (by == "Date modified" or item.ready) else unknown).append(item)
            ordered = sorted(known, key=lambda item: getattr(item, attribute), reverse=descending) + unknown
        self.items[:] = ordered
        if reorder_chosen:
            chosen = set(self.chosen)
            self.chosen[:] = [item for item in ordered if item in chosen]

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
        return [item.pdf_path or item.path for item in self.chosen]
