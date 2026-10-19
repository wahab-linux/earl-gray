import tempfile
import unittest
import zipfile
from pathlib import Path
from queue import Queue
from threading import Event

from pypdf import PdfWriter
from archives import ArchiveStore
from conversion import SlideConverter
from importing import prepare_batch


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.store = ArchiveStore()
        self.addCleanup(self.store.close)
        self.converter = SlideConverter(self.folder / "converted")
        self.pdf = self.folder / "notes.pdf"
        with PdfWriter() as writer:
            writer.add_blank_page(width=100, height=300)
            writer.write(self.pdf)

    def run_batch(self, paths, cancel=None):
        queue = Queue()
        prepare_batch(paths, self.store, self.converter, queue, cancel or Event())
        return list(queue.queue)

    def test_real_file_and_archive_stages_finish_before_done(self):
        archive = self.folder / "documents.zip"
        with zipfile.ZipFile(archive, "w") as output:
            output.write(self.pdf, "nested/archived.PDF")
        events = self.run_batch([self.pdf, archive])
        stages = {event["stage"] for event in events if event["kind"] == "stage"}
        self.assertIn("Reading PDF", stages)
        self.assertIn("Rendering thumbnail", stages)
        fractions = [event["fraction"] for event in events if event["kind"] == "archive" and event["fraction"] is not None]
        self.assertTrue(all(0 <= fraction <= 1 for fraction in fractions))
        self.assertEqual(fractions[-1], 1)
        done = events[-1]
        self.assertEqual(done["kind"], "done")
        self.assertEqual((done["completed"], done["total"], done["ready"]), (2, 2, 2))
        self.assertEqual(done["errors"], [])
        sources = next(event["sources"] for event in events if event["kind"] == "discovered")
        self.assertEqual(sources[0].modified_ns, self.pdf.stat().st_mtime_ns)
        self.assertIsNotNone(sources[1].modified_ns)

    def test_failed_archive_does_not_hide_ready_files(self):
        broken = self.folder / "broken.zip"
        broken.write_bytes(b"not a ZIP")
        events = self.run_batch([broken, self.pdf])
        self.assertEqual(events[-1]["ready"], 1)
        self.assertEqual(len(events[-1]["errors"]), 1)
        self.assertTrue(any(event["kind"] == "archive_error" for event in events))

    def test_cancel_stops_remaining_files_and_reports_completed_count(self):
        cancel = Event()
        original = self.converter.prepare
        def prepare(path, progress=None):
            result = original(path, progress=progress)
            cancel.set()
            return result
        self.converter.prepare = prepare
        events = self.run_batch([self.pdf, self.pdf], cancel)
        self.assertTrue(events[-1]["canceled"])
        self.assertEqual(events[-1]["completed"], 1)
        self.assertEqual(events[-1]["ready"], 1)
        self.assertEqual(events[-1]["total"], 2)
