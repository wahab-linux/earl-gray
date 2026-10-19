import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from library import Library, inspect_pdf
from pdf_merge import merge_pdfs


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.library = Library()
        for index, name in enumerate(("first.pdf", "second.PDF", "third.pdf"), 1):
            path = self.folder / name
            with PdfWriter() as writer:
                writer.add_blank_page(width=100 * index, height=400)
                writer.write(path)
        self.items = self.library.add([self.folder / name for name in ("first.pdf", "second.PDF", "third.pdf")])
        for item in self.items:
            item.size, item.pages, item.preview = inspect_pdf(item.path)
            item.ready = True

    def test_real_thumbnail_and_metadata(self):
        item = self.items[0]
        self.assertEqual(item.size, item.path.stat().st_size)
        self.assertEqual(item.pages, 1)
        self.assertGreater(item.preview.width, 0)
        self.assertLessEqual(item.preview.width, 145)
        self.assertLessEqual(item.preview.height, 169)

    def test_checked_order_controls_real_merge(self):
        a, b, c = self.items
        self.library.toggle(c)
        self.library.toggle(a)
        self.library.toggle(b)
        self.library.toggle(a)  # deselect and compact numbers
        self.library.toggle(a)  # reselected file goes last
        self.library.move(a, -1)
        self.library.drop(b, c)
        self.assertEqual(self.library.chosen, [b, c, a])
        output = self.folder / "result.pdf"
        merge_pdfs(self.library.merge_paths(), output)
        self.assertEqual([float(page.mediabox.width) for page in PdfReader(output).pages], [200, 300, 100])

    def test_removing_checked_file_compacts_selection(self):
        self.library.select_all()
        self.library.remove(self.items[1])
        self.assertEqual(self.library.chosen, [self.items[0], self.items[2]])

    def test_duplicates_and_non_pdfs_ignored(self):
        self.assertEqual(self.library.add([self.items[0].path, self.folder / "notes.txt"]), [])

    def test_unreadable_or_loading_files_not_selected(self):
        first, second, third = self.items
        first.ready = False
        second.error = "Broken PDF"
        self.library.toggle(first)
        self.library.toggle(second)
        self.library.select_all()
        self.assertEqual(self.library.chosen, [third])

    def test_locked_pdf_inspection_rejected(self):
        path = self.folder / "locked.pdf"
        with PdfWriter() as writer:
            writer.add_blank_page(width=100, height=300)
            writer.encrypt("password")
            writer.write(path)
        with self.assertRaisesRegex(ValueError, "Password protected"):
            inspect_pdf(path)
