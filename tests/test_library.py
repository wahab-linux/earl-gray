import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from library import Library, PdfItem, inspect_pdf
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

    def test_natural_name_sort_uses_original_names_and_both_directions(self):
        names = ["10 report.pdf", "5 report.pdf", "4 report.pdf", "2 report.pdf",
                 "chapter 10.PDF", "Chapter 2.pdf", "４ appendix.pdf"]
        # ZIP extraction uses generated names. Those must never control sorting.
        items = [PdfItem(self.folder / f"{i:05d}.pdf", display_name=name, ready=True)
                 for i, name in enumerate(names)]
        self.library.items = items.copy()
        self.library.chosen = [items[0], items[2], items[1]]
        expected = [items[i] for i in (3, 6, 2, 1, 0, 5, 4)]
        self.library.sort()
        self.assertEqual(self.library.items, expected)
        self.assertEqual(self.library.chosen, [items[2], items[1], items[0]])
        self.library.sort(descending=True)
        self.assertEqual(self.library.items, expected[::-1])
        self.assertEqual(self.library.chosen, [items[0], items[1], items[2]])

    def test_metadata_sort_is_numeric_with_name_ties_and_unknowns_last(self):
        a, b, c = self.items
        a.display_name, b.display_name, c.display_name = "10.pdf", "2.pdf", "4.pdf"
        a.size, b.size, c.size = 1024, 12, 1024
        a.pages, b.pages, c.pages = 10, 2, 4
        a.modified_ns, b.modified_ns, c.modified_ns = 30, 10, 20
        missing = PdfItem(self.folder / "missing.pdf", error="Unreadable")
        self.library.items.append(missing)
        for by, ascending, descending in (
            ("Size", [b, c, a], [c, a, b]),
            ("Pages", [b, c, a], [a, c, b]),
            ("Date modified", [b, c, a], [a, c, b]),
        ):
            with self.subTest(by=by):
                self.library.sort(by)
                self.assertEqual(self.library.items, ascending + [missing])
                self.library.sort(by, descending=True)
                self.assertEqual(self.library.items, descending + [missing])

    def test_import_sort_preserves_manual_queue_and_select_all_follows_browser(self):
        a, b, c = self.items
        self.library.chosen = [c, a]
        self.library.sort(reorder_chosen=False)
        self.assertEqual(self.library.chosen, [c, a])
        self.library.select_all()
        self.assertEqual(self.library.chosen, [a, b, c])
        self.library.move(c, -1)
        self.assertEqual(self.library.chosen, [a, c, b])
