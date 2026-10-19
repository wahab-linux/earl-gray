import tempfile
import unittest
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from pdf_merge import merge_pdfs


class MergeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.a = self.make_pdf("a.pdf", 100)
        self.b = self.make_pdf("b.pdf", 200)
        self.output = self.folder / "merged.pdf"

    def make_pdf(self, name, width, password=None):
        path = self.folder / name
        with PdfWriter() as writer:
            writer.add_blank_page(width=width, height=300)
            if password:
                writer.encrypt(password)
            writer.write(path)
        return path

    def test_page_order(self):
        merge_pdfs([self.b, self.a], self.output)
        self.assertEqual([float(p.mediabox.width) for p in PdfReader(self.output).pages], [200, 100])

    def test_source_cannot_be_overwritten(self):
        original = self.a.read_bytes()
        with self.assertRaises(ValueError):
            merge_pdfs([self.a], self.a)
        self.assertEqual(self.a.read_bytes(), original)

    def test_failed_merge_preserves_destination(self):
        self.output.write_bytes(b"existing output")
        broken = self.folder / "broken.pdf"
        broken.write_bytes(b"not a PDF")
        with self.assertRaises(Exception):
            merge_pdfs([self.a, broken], self.output)
        self.assertEqual(self.output.read_bytes(), b"existing output")
        self.assertEqual(set(self.folder.glob("*.pdf")), {self.a, self.b, broken, self.output})

    def test_encrypted_pdf_has_clear_error(self):
        encrypted = self.make_pdf("locked.pdf", 100, "secret")
        with self.assertRaisesRegex(ValueError, "password-protected"):
            merge_pdfs([encrypted], self.output)
        self.assertFalse(self.output.exists())

    def test_empty_input(self):
        with self.assertRaises(ValueError):
            merge_pdfs([], self.output)

    def test_non_pdf_rejected(self):
        with self.assertRaisesRegex(ValueError, "Not a PDF"):
            merge_pdfs([self.folder / "file.txt"], self.output)

    def test_named_sections_point_to_each_documents_first_page(self):
        with PdfWriter() as writer:
            writer.add_blank_page(width=200, height=300)
            writer.add_blank_page(width=300, height=300)
            writer.write(self.b)
        merge_pdfs([self.b, self.a], self.output, ["Workshop.pptx", "Notes.pdf"])
        reader = PdfReader(self.output)
        self.assertEqual([entry.title for entry in reader.outline], ["Workshop.pptx", "Notes.pdf"])
        self.assertEqual([reader.get_destination_page_number(entry) for entry in reader.outline], [0, 2])
        self.assertEqual(len(reader.pages), 3)
        self.assertEqual(reader.trailer["/Root"]["/PageMode"], "/UseOutlines")

    def test_default_sections_use_original_pdf_names(self):
        merge_pdfs([self.b, self.a], self.output)
        self.assertEqual([entry.title for entry in PdfReader(self.output).outline], ["b.pdf", "a.pdf"])

    def test_section_title_mismatch_does_not_change_existing_output(self):
        self.output.write_bytes(b"existing output")
        with self.assertRaisesRegex(ValueError, "one section title"):
            merge_pdfs([self.a], self.output, ["one", "two"])
        self.assertEqual(self.output.read_bytes(), b"existing output")


if __name__ == "__main__":
    unittest.main()
