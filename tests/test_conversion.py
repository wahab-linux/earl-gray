import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter
from conversion import SlideConverter, find_libreoffice, powerpoint_available
from pdf_merge import merge_pdfs

DECK = Path(__file__).parent / "fixtures" / "two-slides.pptx"


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.converter = SlideConverter(self.root / "converted")
        self.pdf = self.root / "source.pdf"
        with PdfWriter() as writer:
            writer.add_blank_page(width=100, height=300)
            writer.write(self.pdf)

    @unittest.skipUnless(find_libreoffice() or powerpoint_available(), "Install LibreOffice or PowerPoint for slide integration tests")
    def test_real_slide_conversion_and_mixed_merge_order(self):
        original = DECK.read_bytes()
        converted, size, pages, preview = self.converter.prepare(DECK)
        self.assertEqual(pages, 2)
        self.assertEqual(size, DECK.stat().st_size)
        self.assertGreater(preview.width, 0)
        target = self.root / "combined.pdf"
        merge_pdfs([self.pdf, converted, self.pdf], target)
        pages = PdfReader(target).pages
        self.assertEqual(len(pages), 4)
        self.assertEqual(float(pages[0].mediabox.width), 100)
        self.assertIn("Slide Alpha", pages[1].extract_text())
        self.assertIn("Slide Beta", pages[2].extract_text())
        self.assertEqual(float(pages[3].mediabox.width), 100)
        self.assertEqual(DECK.read_bytes(), original)

    def test_missing_renderer_does_not_block_pdf(self):
        with patch("conversion.find_libreoffice", return_value=None), patch("conversion.powerpoint_available", return_value=False):
            pdf, _, pages, _ = self.converter.prepare(self.pdf)
            self.assertEqual(pdf, self.pdf)
            self.assertEqual(pages, 1)
            with self.assertRaisesRegex(RuntimeError, "install LibreOffice"):
                self.converter.convert(DECK)
        self.assertEqual(list(self.converter.root.iterdir()), [])

    def test_failed_conversion_cleans_partial_outputs(self):
        with patch("conversion.find_libreoffice", return_value="office"), patch("conversion.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "", "Invalid presentation")):
            with self.assertRaisesRegex(RuntimeError, "could not convert"):
                self.converter.convert(DECK)
        self.assertEqual(list(self.converter.root.iterdir()), [])

    def test_timeout_has_actionable_error(self):
        with patch("conversion.find_libreoffice", return_value="office"), patch("conversion.subprocess.run", side_effect=subprocess.TimeoutExpired("office", 120)):
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                self.converter.convert(DECK)
        self.assertEqual(list(self.converter.root.iterdir()), [])

    def test_powerpoint_uses_script_parameters(self):
        source = self.root / "a slide's $example.pptx"
        shutil.copyfile(DECK, source)
        def run(command, **kwargs):
            self.assertEqual(command[command.index("-SourceFile") + 1], str(source))
            self.assertNotIn("shell", kwargs)
            destination = command[command.index("-OutputFile") + 1]
            shutil.copyfile(self.pdf, destination)
            return subprocess.CompletedProcess(command, 0, "Exported", "")
        with patch("conversion.find_libreoffice", return_value=None), patch("conversion.powerpoint_available", return_value=True), patch("conversion.subprocess.run", side_effect=run):
            self.assertTrue(self.converter.convert(source).exists())
