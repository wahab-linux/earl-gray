"""Desktop integration checks; require a display (or Xvfb on Linux)."""
import tempfile
import os
import time
import tkinter as tk
import customtkinter as ctk
import zipfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter

from app import App


class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_integration = os.environ.get("EARLGRAY_REQUIRE_INTEGRATION_TESTS") == "1"
        if require_integration:
            from conversion import find_libreoffice, powerpoint_available
            if not (find_libreoffice() or powerpoint_available()):
                raise RuntimeError("CI requires a slide renderer; the slide tests must run.")
        try:
            cls.root = ctk.CTk()
        except tk.TclError as error:
            if require_integration:
                raise RuntimeError("CI requires a working desktop display") from error
            raise unittest.SkipTest(f"Desktop display unavailable: {error}")
        try:
            cls.app = App(cls.root)
        except Exception:
            cls.root.destroy()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.app.close()
        cls.app.cleanup_future.result(timeout=10)

    def setUp(self):
        self.root.geometry("1180x800")
        self.app.clear()
        self.app.change_view("Grid")
        if self.app.mode != "light":
            self.app.toggle_theme()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        for index in range(3):
            with PdfWriter() as writer:
                writer.add_blank_page(width=100 + index * 100, height=400)
                writer.write(self.folder / f"sample-{index}.pdf")
        self.app.add(sorted(self.folder.glob("*.pdf")))
        self.wait_for(lambda: not self.app.importing)
        self.assertTrue(all(item.ready for item in self.app.library.items))

    def wait_for(self, condition):
        deadline = time.monotonic() + 60
        while not condition() and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.root.update()
        self.assertTrue(condition(), "UI operation timed out")

    def test_views_numbered_selection_and_save(self):
        first, second, third = self.app.library.items
        self.app.toggle(third)
        self.app.toggle(first)
        for view in ("list", "grid", "list"):
            self.app.view.set(view)
            self.app.render()
            self.root.update()
            cards = self.app.visible_cards
            self.assertEqual(len(cards), 3)
            self.assertTrue(all(card.winfo_ismapped() for card in cards))
            if view == "list":
                self.assertGreater(cards[0].winfo_width(), self.app.canvas.winfo_width() * 0.8)
            self.assertEqual([card.merge_position for card in cards], [2, None, 1])
            self.assertEqual(self.app.library.merge_paths(), [third.path, first.path])
        self.app.active = first
        self.app.move(-1)
        output = self.folder / "merged.pdf"
        with patch("app.filedialog.asksaveasfilename", return_value=str(output)), patch("app.messagebox.showinfo") as notice:
            self.app.save()
            self.assertTrue(self.app.busy)
            self.wait_for(lambda: not self.app.busy)
            notice.assert_called_once()
        self.assertEqual([float(page.mediabox.width) for page in PdfReader(output).pages], [100, 300])
        self.assertEqual(len(self.app.photos), 6)  # both preview sizes were rendered
        self.app.clear()
        self.assertEqual(self.app.library.items, [])
        self.assertEqual(self.app.library.merge_paths(), [])

    def test_rounded_pick_button_changes_selection(self):
        card = self.app.visible_cards[1]
        checkbox = card.selection_button
        checkbox.invoke()
        self.assertEqual(self.app.library.chosen, [self.app.library.items[1]])
        card = self.app.visible_cards[1]
        checkbox = card.selection_button
        checkbox.invoke()
        self.assertEqual(self.app.library.chosen, [])

    def test_drag_reorders_numbered_queue(self):
        from types import SimpleNamespace
        self.app.select_all()
        self.app.view.set("list")
        self.app.render()
        self.root.update()
        first, second, third = self.app.library.items
        cards = self.app.visible_cards
        x = cards[2].winfo_rootx() + cards[2].winfo_width() - 20
        y = cards[2].winfo_rooty() + 20
        self.app.press(SimpleNamespace(x_root=x, y_root=cards[0].winfo_rooty() + 20), first)
        self.app.release(SimpleNamespace(x_root=x, y_root=y))
        self.assertEqual(self.app.library.chosen, [second, third, first])

    def test_cancel_save_keeps_selection(self):
        self.app.select_all()
        with patch("app.filedialog.asksaveasfilename", return_value=""):
            self.app.save()
        self.assertFalse(self.app.busy)
        self.assertEqual(len(self.app.library.chosen), 3)

    def test_circle_theme_toggle_keeps_views_and_order(self):
        self.app.toggle(self.app.library.items[2])
        original = self.app.library.merge_paths()
        self.app.theme_button.invoke()
        self.root.update()
        self.assertEqual(self.app.mode, "dark")
        self.assertEqual(ctk.get_appearance_mode(), "Dark")
        self.assertEqual(self.app.theme_button.cget("corner_radius"), 22)
        self.assertEqual(self.app.theme_button.winfo_width(), self.app.theme_button.winfo_height())
        self.app.change_view("List")
        self.assertEqual(self.app.library.merge_paths(), original)
        self.app.theme_button.invoke()
        self.assertEqual(self.app.mode, "light")
        self.assertEqual(self.app.library.merge_paths(), original)

    def test_zip_import_preview_and_merge(self):
        archive = self.folder / "bundle.zip"
        with zipfile.ZipFile(archive, "w") as output:
            output.write(self.folder / "sample-0.pdf", "nested/cover.PDF")
            output.write(self.folder / "sample-2.pdf", "appendix.pdf")
            output.writestr("notes.txt", "ignore this")
        with patch("app.filedialog.askopenfilenames", return_value=[str(archive)]):
            self.app.add_zip()
        self.wait_for(lambda: not self.app.importing)
        imported = self.app.library.items[3:]
        self.assertEqual([item.name for item in imported], ["cover.PDF", "appendix.pdf"])
        self.assertTrue(all(item.ready and item.preview for item in imported))
        self.assertTrue(all(item.archive == archive.resolve() for item in imported))
        self.app.add([archive])
        self.assertFalse(self.app.importing)
        self.app.toggle(imported[1])
        self.app.toggle(imported[0])
        destination = self.folder / "zip-merged.pdf"
        with patch("app.filedialog.asksaveasfilename", return_value=str(destination)), patch("app.messagebox.showinfo"):
            self.app.save()
            self.wait_for(lambda: not self.app.busy)
        self.assertEqual([float(page.mediabox.width) for page in PdfReader(destination).pages], [300, 100])

    def test_failed_zip_keeps_existing_library(self):
        archive = self.folder / "broken.zip"
        archive.write_bytes(b"not a zip")
        self.app.add([archive])
        self.wait_for(lambda: not self.app.importing)
        self.assertTrue(self.app.last_import_errors)
        self.assertIn("broken.zip", self.app.last_import_errors[0])
        self.assertEqual(len(self.app.library.items), 3)

    def test_repeated_theme_and_view_changes_while_loading(self):
        sources = [item.path for item in self.app.library.items]
        self.app.clear()
        self.app.add(sources)
        for index in range(12):
            self.app.toggle_theme()
            self.app.change_view("List" if index % 2 else "Grid")
            self.root.update()
        self.wait_for(lambda: not self.app.importing)
        self.assertTrue(all(item.ready for item in self.app.library.items))
        self.app.select_all()
        self.assertEqual(self.app.library.merge_paths(), sources)

    def test_open_terminal_button_calls_live_console(self):
        with patch.object(self.app.debug, "open_terminal") as launch:
            self.app.terminal_button.invoke()
            launch.assert_called_once()
        self.app.set_busy(True)
        self.assertEqual(self.app.terminal_button.cget("state"), "normal")
        self.app.set_busy(False)

    def test_pptx_from_zip_merges_with_pdf(self):
        from conversion import find_libreoffice, powerpoint_available
        if not (find_libreoffice() or powerpoint_available()):
            self.skipTest("Install LibreOffice or PowerPoint for slide integration tests")
        archive = self.folder / "slides.zip"
        with zipfile.ZipFile(archive, "w") as output:
            output.write(Path(__file__).parent / "fixtures" / "two-slides.pptx", "Decks/workshop.PPTX")
        self.app.add([archive])
        self.wait_for(lambda: not self.app.importing)
        deck = self.app.library.items[-1]
        self.assertTrue(deck.ready, deck.error)
        self.assertEqual(deck.name, "workshop.PPTX")
        self.assertEqual(deck.pages, 2)
        self.assertTrue(deck.pdf_path.exists())
        self.app.toggle(deck)
        self.app.toggle(self.app.library.items[0])
        destination = self.folder / "mixed.pdf"
        with patch("app.filedialog.asksaveasfilename", return_value=str(destination)), patch("app.messagebox.showinfo"):
            self.app.save()
            self.wait_for(lambda: not self.app.busy)
        pages = PdfReader(destination).pages
        self.assertEqual(len(pages), 3)
        self.assertIn("Slide Alpha", pages[0].extract_text())
        self.assertIn("Slide Beta", pages[1].extract_text())
        self.assertEqual(float(pages[2].mediabox.width), 100)
        reader = PdfReader(destination)
        sections = [entry for entry in reader.outline if not isinstance(entry, list)]
        self.assertEqual([entry.title for entry in sections], ["workshop.PPTX", "sample-0.pdf"])
        self.assertEqual([reader.get_destination_page_number(entry) for entry in sections], [0, 2])

    def test_save_cannot_overwrite_original_presentation(self):
        source = self.folder / "original.pptx"
        source.write_bytes((Path(__file__).parent / "fixtures" / "two-slides.pptx").read_bytes())
        original = source.read_bytes()
        self.app.library.add([source])  # Protect sources even before their conversion is ready.
        self.app.toggle(self.app.library.items[0])
        with patch("app.filedialog.asksaveasfilename", return_value=str(source)), patch("app.messagebox.showerror") as warning:
            self.app.save()
            warning.assert_called_once()
        self.assertFalse(self.app.busy)
        self.assertEqual(source.read_bytes(), original)

    def test_loading_screen_blocks_merge_until_every_file_and_card_is_ready(self):
        from threading import Event
        entered, release = Event(), Event()
        source = self.folder / "additional.pdf"
        source.write_bytes((self.folder / "sample-0.pdf").read_bytes())
        self.app.select_all()
        previous_cards = list(self.app.visible_cards)
        original = self.app.converter.prepare
        def delayed(path, progress=None):
            if progress:
                progress("Reading PDF", "Checking page count")
            entered.set()
            if not release.wait(10):
                raise RuntimeError("Test preparation gate timed out")
            return original(path, progress=progress)
        try:
            with patch.object(self.app.converter, "prepare", side_effect=delayed):
                self.app.add([source])
                self.wait_for(entered.is_set)
                self.wait_for(lambda: "additional.pdf" in self.app.loading.detail.cget("text"))
                self.assertTrue(self.app.loading.winfo_ismapped())
                self.assertFalse(self.app.content._parent_frame.winfo_ismapped())
                self.assertEqual(self.app.merge_button.cget("state"), "disabled")
                self.assertEqual(self.app.terminal_button.cget("state"), "normal")
                with patch("app.filedialog.asksaveasfilename") as save_dialog:
                    self.app.save()
                    save_dialog.assert_not_called()
                self.app.toggle(self.app.library.items[0])
                self.assertEqual(len(self.app.library.chosen), 3)
                release.set()
                self.wait_for(lambda: not self.app.importing)
        finally:
            release.set()
            self.wait_for(lambda: not self.app.importing)
        self.assertFalse(self.app.loading.winfo_ismapped())
        self.assertEqual(self.app.merge_button.cget("state"), "normal")
        self.assertEqual(self.app.visible_cards[:3], previous_cards)
        self.assertTrue(all(item.ready for item in self.app.library.items))

    def test_scrolling_selection_and_view_switches_preserve_card_widgets(self):
        sources = []
        for index in range(36):
            source = self.folder / f"extra-{index:02d}.pdf"
            source.write_bytes((self.folder / "sample-0.pdf").read_bytes())
            sources.append(source)
        self.app.add(sources)
        self.wait_for(lambda: not self.app.importing)
        cards = list(self.app.visible_cards)
        self.app.canvas.yview_moveto(0.55)
        self.root.update()
        before = self.app.canvas.yview()[0]
        self.assertGreater(before, 0.1)
        with patch.object(self.app, "card", side_effect=AssertionError("Browsing rebuilt a card")):
            for _ in range(4):
                self.app.toggle(self.app.library.items[-1])
                self.root.update()
                self.assertAlmostEqual(self.app.canvas.yview()[0], before, places=4)
            self.app.select_all()
            self.app.move(-1)
            self.app.toggle_theme()
            self.root.update()
            self.assertAlmostEqual(self.app.canvas.yview()[0], before, places=4)
            self.app.change_view("List")
            self.root.update()
            self.assertEqual(self.app.visible_cards, cards)
            self.app.change_view("Grid")
            self.root.update()
            self.assertAlmostEqual(self.app.canvas.yview()[0], before, places=4)
            self.assertEqual(self.app.visible_cards, cards)
            self.assertTrue(all(card.winfo_ismapped() for card in cards))

    def test_import_error_is_classified_before_merge_unlocks(self):
        invalid = self.folder / "broken.pdf"
        invalid.write_bytes(b"broken PDF")
        self.app.add([invalid])
        self.wait_for(lambda: not self.app.importing)
        self.assertEqual(len(self.app.last_import_errors), 1)
        failed = self.app.library.items[-1]
        self.assertTrue(failed.error)
        self.assertFalse(failed.ready)
        self.app.select_all()
        self.assertNotIn(failed, self.app.library.chosen)
        self.assertEqual(self.app.merge_button.cget("state"), "normal")
        self.assertEqual(self.app.visible_cards[-1].selection_button.cget("state"), "disabled")

    def test_cancel_remaining_keeps_existing_and_completed_files(self):
        from threading import Event
        entered, release = Event(), Event()
        sources = []
        for name in ("first-new.pdf", "second-new.pdf"):
            path = self.folder / name
            path.write_bytes((self.folder / "sample-0.pdf").read_bytes())
            sources.append(path)
        original = self.app.converter.prepare
        def delayed(path, progress=None):
            entered.set()
            if not release.wait(10):
                raise RuntimeError("Test cancellation gate timed out")
            return original(path, progress=progress)
        try:
            with patch.object(self.app.converter, "prepare", side_effect=delayed):
                self.app.add(sources)
                self.wait_for(entered.is_set)
                self.app.loading.cancel_button.invoke()
                self.assertTrue(self.app.import_cancel.is_set())
                release.set()
                self.wait_for(lambda: not self.app.importing)
        finally:
            release.set()
            self.wait_for(lambda: not self.app.importing)
        self.assertEqual(len(self.app.library.items), 4)
        self.assertIn(sources[0], [item.path for item in self.app.library.items])
        self.assertNotIn(sources[1], [item.path for item in self.app.library.items])
        self.assertIn("canceled", self.app.notice.get())
