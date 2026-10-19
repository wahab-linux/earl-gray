"""Earl Gray: a local PDF merger with grid and list previews."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font

from PIL import Image, ImageTk

from library import Library, format_size, inspect_pdf
from pdf_merge import merge_pdfs

BG = "#f5f6fa"
INK = "#222b3d"
MUTED = "#626e83"
ACCENT = "#465cda"


class App:
    def __init__(self, root):
        self.root = root
        self.library = Library()
        # PDFium calls are serialized: its renderer is not thread safe.
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.pending = []
        self.photos = {}
        self.active = None
        self.busy = False
        self.drag_source = None
        self.resize_job = None
        self.columns = 0
        self.view = tk.StringVar(value="grid")
        root.title("Earl Gray · PDF merger")
        root.geometry("1000x720")
        root.minsize(760, 560)
        root.configure(bg=BG)
        available = {name.casefold(): name for name in font.families(root)}
        self.font = next((available[name.casefold()] for name in ("Segoe UI", "SF Pro Text", "DejaVu Sans", "Helvetica") if name.casefold() in available), "TkDefaultFont")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", font=(self.font, 10), background=BG, foreground=INK)
        style.configure("TButton", padding=(12, 8))
        style.configure("Accent.TButton", background=ACCENT, foreground="white")
        style.map("Accent.TButton", background=[("active", "#3549bd")])
        style.configure("Title.TLabel", font=(self.font, 26, "bold"))
        style.configure("Muted.TLabel", foreground=MUTED)
        frame = ttk.Frame(root, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Earl Gray", style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text="A little order. One perfect PDF. Everything stays on your device.", style="Muted.TLabel").pack(anchor="w", pady=(4, 18))
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x")
        self.controls = []
        self.button(toolbar, "Add PDFs", self.add_files).pack(side="left")
        self.button(toolbar, "Open folder", self.add_folder).pack(side="left", padx=8)
        for value, label in (("list", "List"), ("grid", "Grid")):
            radio = ttk.Radiobutton(toolbar, text=label, value=value, variable=self.view, command=self.render)
            radio.pack(side="right", padx=6)
            self.controls.append(radio)
        ttk.Label(frame, text="Tick PDFs in merge order. The number beside each tick is its position.", style="Muted.TLabel").pack(anchor="w", pady=(18, 5))
        ttk.Label(frame, text="Click a card, then move it earlier/later, or drag between checked PDFs.", style="Muted.TLabel").pack(anchor="w", pady=(0, 12))
        panel = ttk.Frame(frame)
        panel.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(panel, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(panel, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.content = tk.Frame(self.canvas, bg=BG)
        self.window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self.resize)
        root.bind("<MouseWheel>", self.wheel)
        root.bind("<Button-4>", lambda event: self.canvas.yview_scroll(-1, "units"))
        root.bind("<Button-5>", lambda event: self.canvas.yview_scroll(1, "units"))
        selection = ttk.Frame(frame)
        selection.pack(fill="x", pady=(12, 8))
        self.button(selection, "Select all", self.select_all).pack(side="left")
        self.button(selection, "Deselect all", self.deselect_all).pack(side="left", padx=6)
        self.button(selection, "Remove", self.remove).pack(side="left")
        self.button(selection, "Clear", self.clear).pack(side="left", padx=6)
        footer = ttk.Frame(frame)
        footer.pack(fill="x")
        self.button(footer, "Move earlier", lambda: self.move(-1)).pack(side="left")
        self.button(footer, "Move later", lambda: self.move(1)).pack(side="left", padx=6)
        self.merge_button = self.button(footer, "Merge & save...", self.save, "Accent.TButton")
        self.merge_button.pack(side="right")
        self.status = tk.StringVar()
        ttk.Label(frame, textvariable=self.status, style="Muted.TLabel", wraplength=700).pack(anchor="w", pady=(12, 0))
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.render()
        root.after(100, self.poll_previews)

    def button(self, parent, text, command, style="TButton"):
        button = ttk.Button(parent, text=text, command=command, style=style)
        self.controls.append(button)
        return button

    def add_files(self):
        self.add(filedialog.askopenfilenames(title="Select PDFs", filetypes=[("PDF files", "*.pdf")]))

    def add_folder(self):
        folder = filedialog.askdirectory(title="Open a folder containing PDFs")
        if folder:
            try:
                self.add(sorted((p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() == ".pdf"), key=lambda p: p.name.casefold()))
            except OSError as error:
                messagebox.showerror("Cannot open folder", str(error))

    def add(self, paths):
        if self.busy:
            return
        for item in self.library.add(paths):
            self.pending.append((item, self.executor.submit(inspect_pdf, item.path)))
        self.render()

    def poll_previews(self):
        changed = False
        for item, future in list(self.pending):
            if not future.done():
                continue
            self.pending.remove((item, future))
            if item not in self.library.items:
                continue
            try:
                item.size, item.pages, item.preview = future.result()
                item.ready = True
            except Exception as error:
                item.error = str(error) or "Cannot read this PDF."
            changed = True
        if changed:
            self.render()
        self.root.after(100, self.poll_previews)

    def resize(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)
        columns = max(1, event.width // 210)
        if columns != self.columns:
            self.columns = columns
            if self.resize_job:
                self.root.after_cancel(self.resize_job)
            self.resize_job = self.root.after(80, self.render)

    def wheel(self, event):
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def summary(self):
        chosen = self.library.chosen
        loading = sum(not item.ready and not item.error for item in self.library.items)
        errors = sum(bool(item.error) for item in self.library.items)
        text = f"{len(chosen)} selected · {sum(item.pages for item in chosen)} pages · {format_size(sum(item.size for item in chosen))}"
        if loading:
            text += f" · Loading {loading} preview(s)..."
        if errors:
            text += f" · {errors} unreadable PDF(s)"
        self.status.set("Merging PDFs..." if self.busy else text)
        self.merge_button.state(["disabled"] if self.busy or not chosen else ["!disabled"])

    def render(self):
        self.resize_job = None
        offset = self.canvas.yview()[0]
        for child in self.content.winfo_children():
            child.destroy()
        # Reset column weights when switching between layouts.
        for column in range(max(self.content.grid_size()[0], self.columns, 1) + 1):
            self.content.columnconfigure(column, weight=0, uniform="")
        if not self.library.items:
            tk.Label(self.content, text="Make room for a little order.\n\nAdd PDFs or open a folder to begin.", bg=BG, fg=MUTED, font=(self.font, 14), pady=70).pack(fill="both", expand=True)
        else:
            grid = self.view.get() == "grid"
            columns = max(self.columns, 1) if grid else 1
            for column in range(columns):
                self.content.columnconfigure(column, weight=1, uniform="cards")
            for index, item in enumerate(self.library.items):
                self.card(item, grid).grid(row=index // columns, column=index % columns, sticky="nsew", padx=5, pady=5)
        self.summary()
        self.content.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.canvas.yview_moveto(offset)

    def photo(self, item, grid):
        key = (item.path, grid)
        if key not in self.photos:
            image = item.preview.copy()
            image.thumbnail((144, 168) if grid else (52, 64), Image.Resampling.LANCZOS)
            self.photos[key] = ImageTk.PhotoImage(image, master=self.root)
        return self.photos[key]

    def card(self, item, grid):
        focused = item is self.active
        card = tk.Frame(self.content, bg="white", highlightbackground=ACCENT if focused else "#dfe3ed", highlightthickness=2 if focused else 1, padx=12, pady=10)
        card.pdf_item = item
        checked = item in self.library.chosen
        position = self.library.chosen.index(item) + 1 if checked else None
        variable = tk.BooleanVar(value=checked)
        tick = tk.Checkbutton(card, text=f"Merge #{position}" if checked else "Include PDF", variable=variable, command=lambda: self.toggle(item), bg="white", activebackground="white", fg=ACCENT if checked else MUTED, font=(self.font, 10, "bold"), anchor="w", takefocus=True)
        tick.variable = variable
        if self.busy or not item.ready or item.error:
            tick.configure(state="disabled")
        tick.grid(row=0, column=0, columnspan=2 if grid else 1, sticky="w")
        preview = tk.Label(card, bg="#f0f2f7", fg=MUTED, text="PDF" if item.error else "Loading...", width=18 if grid else 7, height=9 if grid else 3)
        if item.preview is not None:
            preview.configure(image=self.photo(item, grid), text="", width=160 if grid else 56, height=174 if grid else 68)
        preview.grid(row=1 if grid else 0, column=0 if grid else 1, sticky="n", pady=6, padx=4)
        details = tk.Frame(card, bg="white")
        details.grid(row=2 if grid else 0, column=0 if grid else 2, sticky="nsew", padx=(0 if grid else 14, 0))
        card.columnconfigure(0 if grid else 2, weight=1)
        title = tk.Label(details, text=item.path.name, bg="white", fg=INK, font=(self.font, 11, "bold"), wraplength=160 if grid else 390, justify="left", anchor="w")
        title.pack(fill="x", pady=(2, 6))
        metadata = f"{item.pages} page{'s' if item.pages != 1 else ''} · {format_size(item.size)}" if item.ready else "Reading PDF..."
        tk.Label(details, text=metadata if not item.error else "Cannot include this PDF", bg="white", fg=MUTED if not item.error else "#b33443", anchor="w").pack(fill="x")
        if item.error:
            tk.Label(details, text=item.error, bg="white", fg="#b33443", wraplength=160 if grid else 390, justify="left").pack(anchor="w", pady=4)
        if not grid:
            tk.Label(details, text=str(item.path.parent), bg="white", fg=MUTED, wraplength=390, anchor="w", justify="left").pack(fill="x", pady=(4, 0))
        self.bind_card(card, item, tick)
        return card

    def bind_card(self, widget, item, tick):
        if widget is tick:
            return
        widget.bind("<ButtonPress-1>", lambda event: self.press(event, item))
        widget.bind("<ButtonRelease-1>", self.release)
        for child in widget.winfo_children():
            self.bind_card(child, item, tick)

    def press(self, event, item):
        if not self.busy:
            self.active = item
            self.drag_source = (item, event.x_root, event.y_root)

    def release(self, event):
        if self.busy or self.drag_source is None:
            return
        item, x, y = self.drag_source
        self.drag_source = None
        if abs(event.x_root - x) + abs(event.y_root - y) > 8:
            widget = self.root.winfo_containing(event.x_root, event.y_root)
            while widget is not None and not hasattr(widget, "pdf_item"):
                widget = widget.master
            if widget is not None:
                self.library.drop(item, widget.pdf_item)
        self.render()

    def toggle(self, item):
        if not self.busy:
            self.active = item
            self.library.toggle(item)
            self.render()

    def select_all(self):
        self.library.select_all()
        self.render()

    def deselect_all(self):
        self.library.chosen.clear()
        self.render()

    def move(self, delta):
        self.library.move(self.active, delta)
        self.render()

    def remove(self):
        if self.active:
            item = self.active
            self.library.remove(item)
            for grid in (True, False):
                self.photos.pop((item.path, grid), None)
            self.active = None
            self.render()

    def clear(self):
        for _, future in self.pending:
            future.cancel()
        self.pending.clear()
        self.library = Library()
        self.active = None
        self.photos.clear()
        self.render()

    def set_busy(self, busy):
        self.busy = busy
        for control in self.controls:
            control.state(["disabled"] if busy else ["!disabled"])
        self.render()

    def save(self):
        paths = self.library.merge_paths()
        if self.busy or not paths:
            return
        target = filedialog.asksaveasfilename(title="Save merged PDF", defaultextension=".pdf", initialfile="merged.pdf", filetypes=[("PDF files", "*.pdf")])
        if not target:
            return
        self.set_busy(True)
        future = self.executor.submit(merge_pdfs, paths, target)
        self.root.after(100, self.poll_merge, future, target)

    def poll_merge(self, future, target):
        if not future.done():
            self.root.after(100, self.poll_merge, future, target)
            return
        self.set_busy(False)
        try:
            future.result()
        except Exception as error:
            self.status.set("Merge failed. Your source PDFs are unchanged.")
            messagebox.showerror("Could not merge PDFs", str(error))
        else:
            self.status.set(f"Saved: {target}")
            messagebox.showinfo("PDF saved", f"Merged PDF saved to:\n{target}")

    def close(self):
        if self.busy:
            messagebox.showinfo("Merge in progress", "Please wait for the merge to finish before closing.")
            return
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


if __name__ == "__main__":
    App(tk.Tk()).root.mainloop()
