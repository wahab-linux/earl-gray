"""Desktop integration checks; require a display (or Xvfb on Linux)."""
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter

from app import App


class DesktopTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Desktop display unavailable: {error}")
        self.app = App(self.root)
        self.addCleanup(self.app.close)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        for index in range(3):
            with PdfWriter() as writer:
                writer.add_blank_page(width=100 + index * 100, height=400)
                writer.write(self.folder / f"sample-{index}.pdf")
        self.app.add(sorted(self.folder.glob("*.pdf")))
        self.wait_for(lambda: not self.app.pending)
        self.assertTrue(all(item.ready for item in self.app.library.items))

    def wait_for(self, condition):
        deadline = time.monotonic() + 10
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
            cards = self.app.content.winfo_children()
            self.assertEqual(len(cards), 3)
            self.assertTrue(all(card.winfo_ismapped() for card in cards))
            if view == "list":
                self.assertGreater(cards[0].winfo_width(), self.app.canvas.winfo_width() * 0.8)
            ticks = [widget for card in cards for widget in card.winfo_children() if isinstance(widget, tk.Checkbutton)]
            self.assertEqual([tick.cget("text") for tick in ticks], ["Merge #2", "Include PDF", "Merge #1"])
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

    def test_native_checkbutton_changes_selection(self):
        card = self.app.content.winfo_children()[1]
        checkbox = next(widget for widget in card.winfo_children() if isinstance(widget, tk.Checkbutton))
        checkbox.invoke()
        self.assertEqual(self.app.library.chosen, [self.app.library.items[1]])
        card = self.app.content.winfo_children()[1]
        checkbox = next(widget for widget in card.winfo_children() if isinstance(widget, tk.Checkbutton))
        checkbox.invoke()
        self.assertEqual(self.app.library.chosen, [])

    def test_drag_reorders_numbered_queue(self):
        from types import SimpleNamespace
        self.app.select_all()
        self.app.view.set("list")
        self.app.render()
        self.root.update()
        first, second, third = self.app.library.items
        cards = self.app.content.winfo_children()
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
