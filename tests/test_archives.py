import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from archives import ArchiveStore
from library import inspect_pdf
from pypdf import PdfWriter


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.store = ArchiveStore()
        self.addCleanup(self.store.close)
        self.pdf = self.folder / "source.pdf"
        with PdfWriter() as writer:
            writer.add_blank_page(width=100, height=300)
            writer.write(self.pdf)
        self.archive = self.folder / "bundle.zip"

    def test_nested_pdfs_only_and_original_names(self):
        with zipfile.ZipFile(self.archive, "w") as output:
            output.write(self.pdf, "folder/one.PDF")
            output.write(self.pdf, "other/one.PDF")
            output.writestr("notes.txt", "skip")
        original = self.archive.read_bytes()
        imported = self.store.extract(self.archive)
        self.assertEqual([item.name for item in imported], ["one.PDF", "one.PDF"])
        self.assertNotEqual(imported[0].path, imported[1].path)
        for item in imported:
            self.assertTrue(item.path.is_relative_to(self.store.root))
            self.assertEqual(inspect_pdf(item.path)[1], 1)
        self.assertEqual(self.archive.read_bytes(), original)

    def test_traversal_and_absolute_paths_rejected(self):
        for name in ("../outside.pdf", "/outside.pdf", "C:/outside.pdf", "..\\outside.pdf"):
            with self.subTest(name=name):
                with zipfile.ZipFile(self.archive, "w") as output:
                    output.write(self.pdf, "good.pdf")
                    output.writestr(name, self.pdf.read_bytes())
                with self.assertRaisesRegex(ValueError, "unsafe"):
                    self.store.extract(self.archive)
                self.assertEqual(list(self.store.root.iterdir()), [])

    def test_pdf_symlink_rejected(self):
        entry = zipfile.ZipInfo("link.pdf")
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(self.archive, "w") as output:
            output.writestr(entry, "outside.pdf")
        with self.assertRaisesRegex(ValueError, "links"):
            self.store.extract(self.archive)

    def test_size_limits_before_extraction(self):
        with zipfile.ZipFile(self.archive, "w") as output:
            output.write(self.pdf, "one.pdf")
            output.write(self.pdf, "two.pdf")
        for setting, limit in (("MAX_PDFS", 1), ("MAX_PDF_BYTES", 1), ("MAX_TOTAL_BYTES", 1)):
            with self.subTest(setting=setting), patch(f"archives.{setting}", limit):
                with self.assertRaises(ValueError):
                    self.store.extract(self.archive)
                self.assertEqual(list(self.store.root.iterdir()), [])

    def test_crc_failure_cleans_partial_output(self):
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_STORED) as output:
            output.writestr("broken.pdf", b"PDF CONTENT")
        data = self.archive.read_bytes().replace(b"PDF CONTENT", b"BAD CONTENT")
        self.archive.write_bytes(data)
        with self.assertRaises(zipfile.BadZipFile):
            self.store.extract(self.archive)
        self.assertEqual(list(self.store.root.iterdir()), [])

    def test_empty_archive_and_cleanup(self):
        with zipfile.ZipFile(self.archive, "w") as output:
            output.writestr("notes.txt", "not a PDF")
        self.assertEqual(self.store.extract(self.archive), [])
        self.store.close()
        self.assertFalse(self.store.root.exists())
