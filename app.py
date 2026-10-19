"""Earl Gray: a rounded, local-first desktop PDF workspace."""
from concurrent.futures import ThreadPoolExecutor
import gc
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, font

import customtkinter as ctk
from PIL import Image, ImageTk

from archives import ArchiveStore
from library import Library, format_size
from conversion import SlideConverter
from diagnostics import DebugLog
from pdf_merge import merge_pdfs
from ui import icon, empty_art, CircleButton, detach_images

BG = ("#F4F7FC", "#11151E")
SURFACE = ("#FFFFFF", "#1B2230")
INK = ("#202B40", "#EDF2FC")
MUTED = ("#647189", "#A3B0C6")
BORDER = ("#E1E7F1", "#303C50")
SOFT = ("#EBF0F8", "#252F40")
BLUE = "#1967D2"
GREEN = "#188038"
RED = "#D93025"
YELLOW = "#FBBC05"
BLUE_TEXT = ("#1967D2", "#8AB4F8")


class App:
    def __init__(self, root, debug_log=None):
        self.root = root
        self.debug = debug_log or DebugLog()
        self.root.report_callback_exception = self.callback_error
        icon.cache_clear()  # CTk image caches belong to this Tk interpreter.
        self.gc_was_enabled = gc.isenabled()
        self.library = Library()
        self.archives = ArchiveStore()
        self.converter = SlideConverter(self.archives.root / "slides", self.debug.logger)
        # Both ZIP import and PDFium rendering run on this one worker.
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.pending = []
        self.imports = []
        self.photos = {}
        self.active = None
        self.busy = False
        self.closed = False
        self.drag_source = None
        self.resize_job = None
        self.columns = 0
        self.mode = "light"
        self.view = tk.StringVar(master=root, value="grid")
        self.status = tk.StringVar(master=root)
        self.notice = tk.StringVar(master=root, value="Your files stay on your device. Always.")
        ctk.set_appearance_mode("light")
        root.title("Earl Gray | A little order, one perfect PDF")
        root.geometry("1180x800")
        root.minsize(940, 660)
        root.configure(fg_color=BG)
        self.set_window_icon()
        available = {name.casefold(): name for name in font.families(root)}
        self.font = next((available[name.casefold()] for name in ("Segoe UI", "SF Pro Text", "DejaVu Sans", "Helvetica") if name.casefold() in available), "Helvetica")
        self.controls = []
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(0, weight=1)
        self.build_sidebar()
        self.build_workspace()
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.render()
        # Tk image finalizers must run on the UI thread, even during cyclic GC.
        gc.disable()
        self.preview_job = root.after(80, self.poll_previews)
        self.collect_job = root.after(1000, self.collect_images)

    def set_window_icon(self):
        import sys
        assets = Path(__file__).resolve().parent / "assets"
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("WahabLinux.EarlGray")
            self.root.iconbitmap(str(assets / "earl-gray.ico"))
        else:
            with Image.open(assets / "tea.png") as image:
                self.window_icon = ImageTk.PhotoImage(image.copy(), master=self.root)
            self.root.iconphoto(True, self.window_icon)
        self.debug.logger.info("Tea app icon loaded.")

    def callback_error(self, exception, value, traceback):
        self.debug.logger.error("Unhandled UI error", exc_info=(exception, value, traceback))
        messagebox.showerror("Something went wrong", f"{value}\n\nOpen terminal for details.\nLog: {self.debug.path}")

    def open_terminal(self):
        try:
            self.debug.open_terminal()
            self.notice.set("Debug terminal opened. It shows the live session log.")
        except (OSError, RuntimeError) as error:
            self.debug.logger.exception("Could not open debug terminal")
            messagebox.showerror("Could not open terminal", f"{error}\n\nLog file: {self.debug.path}")

    def collect_images(self):
        gc.collect()
        if not self.closed:
            self.collect_job = self.root.after(1000, self.collect_images)

    def text(self, parent, text="", size=13, bold=False, color=INK, **kwargs):
        return ctk.CTkLabel(parent, text=text, text_color=color, font=(self.font, size, "bold" if bold else "normal"), **kwargs)

    def button(self, parent, text, command, color=None, image=None, width=120, **kwargs):
        color = color or SOFT
        button = ctk.CTkButton(parent, text=text, command=command, width=width, height=42,
                               corner_radius=13, fg_color=color, hover_color=kwargs.pop("hover_color", BORDER),
                               text_color=kwargs.pop("text_color", INK), font=(self.font, 13, "bold"),
                               image=image, **kwargs)
        self.controls.append(button)
        return button

    def build_sidebar(self):
        side = ctk.CTkFrame(self.root, width=214, corner_radius=0, fg_color=SURFACE)
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)
        side.grid_columnconfigure(0, weight=1)
        side.grid_rowconfigure(8, weight=1)
        brand = ctk.CTkFrame(side, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=22, pady=(30, 28))
        self.text(brand, "", image=icon("logo", size=30)).pack(side="left")
        self.text(brand, "earl gray", 23, True).pack(side="left", padx=10)
        self.text(side, "A LITTLE LESS SCATTERED.", 10, True, MUTED).grid(row=1, column=0, sticky="w", padx=24, pady=(0, 28))
        self.button(side, "Add files", self.add_files, BLUE, icon("plus"), width=168,
                    text_color="white", hover_color="#185ABC").grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        self.button(side, "Add ZIP", self.add_zip, YELLOW, icon("zip", "#33280B"), width=168,
                    text_color="#33280B", hover_color="#F4B400").grid(row=3, column=0, padx=20, pady=5, sticky="ew")
        self.button(side, "Open folder", self.add_folder, SOFT, icon("folder", MUTED), width=168).grid(row=4, column=0, padx=20, pady=5, sticky="ew")
        guide = ctk.CTkFrame(side, fg_color=BG, corner_radius=18)
        guide.grid(row=5, column=0, padx=20, pady=28, sticky="ew")
        self.text(guide, "THREE LITTLE STEPS", 10, True, MUTED).pack(anchor="w", padx=16, pady=(18, 12))
        for number, label, color in (("1", "Bring your files", BLUE), ("2", "Pick the order", RED), ("3", "Save one file", GREEN)):
            row = ctk.CTkFrame(guide, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=(0, 14))
            self.text(row, number, 11, True, "white", fg_color=color, corner_radius=12, width=24, height=24).pack(side="left")
            self.text(row, label, 12, color=INK).pack(side="left", padx=8)
        privacy = ctk.CTkFrame(side, fg_color="transparent")
        privacy.grid(row=9, column=0, padx=22, pady=(0, 16), sticky="ew")
        self.text(privacy, "", image=icon("shield", ("#188038", "#81C995"), 22)).pack(anchor="w")
        self.text(privacy, "Private by default", 12, True).pack(anchor="w", pady=(6, 0))
        self.text(privacy, "No uploads. No accounts.\nJust you and your pages.", 11, color=MUTED, justify="left").pack(anchor="w", pady=4)
        self.terminal_button = self.button(side, "Open terminal", self.open_terminal, SOFT, icon("terminal", MUTED), width=168)
        self.terminal_button.grid(row=7, column=0, padx=20, pady=5, sticky="ew")
        self.controls.remove(self.terminal_button)  # Diagnostics remains available during a merge.
        self.button(side, "Clear workspace", self.clear, ("#FCE8E6", "#39262B"), icon("trash", ("#B3261E", "#F28B82")), width=168,
                    text_color=("#B3261E", "#F28B82"), hover_color=("#F9D5D1", "#503037")).grid(row=10, column=0, padx=20, pady=(0, 24), sticky="ew")

    def build_workspace(self):
        main = ctk.CTkFrame(self.root, fg_color="transparent", corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew", padx=28, pady=(26, 16))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(3, weight=1)
        header = ctk.CTkFrame(main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        heading = ctk.CTkFrame(header, fg_color="transparent")
        heading.pack(side="left")
        self.text(heading, "Your PDFs, together.", 30, True).pack(anchor="w")
        self.text(heading, "A little order. One perfect PDF.", 13, color=MUTED).pack(anchor="w", pady=(3, 0))
        self.theme_button = CircleButton(header, text="", image=icon("sun", "#E6A700", 22), width=44, height=44,
                                        corner_radius=22, fg_color=SURFACE, hover_color=SOFT, border_width=1,
                                        border_color=BORDER, command=self.toggle_theme)
        self.theme_button.pack(side="right", padx=(12, 0))
        self.mode_label = self.text(header, "Light mode", 12, color=MUTED)
        self.mode_label.pack(side="right")
        banner = ctk.CTkFrame(main, fg_color=("#E8F0FE", "#1B2D49"), corner_radius=20)
        banner.grid(row=1, column=0, sticky="ew", pady=(22, 20))
        self.text(banner, "", image=icon("merge", BLUE_TEXT, 30), width=58).pack(side="left", padx=(12, 0), pady=16)
        words = ctk.CTkFrame(banner, fg_color="transparent")
        words.pack(side="left", fill="x", expand=True, padx=4, pady=14)
        self.text(words, "Good things come together.", 16, True, BLUE_TEXT).pack(anchor="w")
        self.text(words, "PDFs, slides, or ZIPs in. One beautifully ordered PDF out.", 12, color=MUTED).pack(anchor="w", pady=(2, 0))
        self.text(banner, "", image=icon("logo", size=24)).pack(side="right", padx=22)
        toolbar = ctk.CTkFrame(main, fg_color="transparent")
        toolbar.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        self.count_label = self.text(toolbar, "Your library", 17, True)
        self.count_label.pack(side="left")
        self.layout_switch = ctk.CTkSegmentedButton(toolbar, values=["Grid", "List"], command=self.change_view,
                         width=146, height=34, corner_radius=12, fg_color=SOFT, selected_color=SURFACE,
                         selected_hover_color=SURFACE, unselected_color=SOFT, unselected_hover_color=BORDER,
                         text_color=INK, font=(self.font, 12, "bold"), dynamic_resizing=False)
        self.layout_switch.set("Grid")
        self.layout_switch.pack(side="right")
        self.controls.append(self.layout_switch)
        for label, command in (("None", self.deselect_all), ("Select all", self.select_all)):
            control = ctk.CTkButton(toolbar, text=label, width=70, height=32, corner_radius=10, fg_color="transparent",
                                    hover_color=SOFT, text_color=BLUE_TEXT, font=(self.font, 12), command=command)
            control.pack(side="right", padx=5)
            self.controls.append(control)
        self.content = ctk.CTkScrollableFrame(main, fg_color=BG, corner_radius=0, scrollbar_button_color=BORDER,
                                             scrollbar_button_hover_color=MUTED)
        self.content.grid(row=3, column=0, sticky="nsew", padx=0)
        self.canvas = self.content._parent_canvas
        self.canvas.bind("<Configure>", self.resize, add="+")
        self.text(main, "Tick to pick. Numbers show merge order. Drag checked cards to rearrange.", 11, color=MUTED).grid(row=4, column=0, sticky="w", pady=(10, 12))
        footer = ctk.CTkFrame(main, fg_color=SURFACE, corner_radius=20, border_width=1, border_color=BORDER)
        footer.grid(row=5, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        info = ctk.CTkFrame(footer, fg_color="transparent")
        info.grid(row=0, column=0, sticky="w", padx=18, pady=14)
        self.selection_label = self.text(info, "Ready when you are", 14, True)
        self.selection_label.pack(anchor="w")
        self.text(info, textvariable=self.status, size=11, color=MUTED).pack(anchor="w", pady=(3, 0))
        actions = ctk.CTkFrame(footer, fg_color="transparent")
        actions.grid(row=0, column=1, padx=(0, 12), pady=12)
        self.button(actions, "", lambda: self.move(-1), image=icon("up", MUTED), width=38).pack(side="left", padx=3)
        self.button(actions, "", lambda: self.move(1), image=icon("down", MUTED), width=38).pack(side="left", padx=3)
        self.button(actions, "", self.remove, ("#FCE8E6", "#39262B"), icon("trash", ("#B3261E", "#F28B82")), width=38,
                    hover_color=("#F9D5D1", "#503037")).pack(side="left", padx=(3, 10))
        self.merge_button = self.button(actions, "Merge & save", self.save, GREEN, icon("arrow"), width=156,
                                       text_color="white", hover_color="#137333")
        self.merge_button.pack(side="left")
        self.notice_label = self.text(main, textvariable=self.notice, size=11, color=MUTED, anchor="w", wraplength=780)
        self.notice_label.grid(row=6, column=0, sticky="ew", pady=(10, 0))
        self.progress = ctk.CTkProgressBar(main, height=3, corner_radius=2, mode="indeterminate", progress_color=BLUE,
                                          fg_color=SOFT)
        self.progress.grid(row=7, column=0, sticky="ew", pady=(6, 0))
        self.progress.set(0)

    def toggle_theme(self):
        self.mode = "dark" if self.mode == "light" else "light"
        ctk.set_appearance_mode(self.mode)
        self.theme_button.configure(image=icon("moon", size=22) if self.mode == "dark" else icon("sun", "#E6A700", 22))
        self.mode_label.configure(text=f"{self.mode.title()} mode")
        self.debug.logger.debug("Theme changed to %s", self.mode)
        self.render()

    def change_view(self, value):
        self.view.set(value.lower())
        self.render()

    def add_files(self):
        self.add(filedialog.askopenfilenames(title="Add PDFs, PowerPoint slides, or ZIP archives", filetypes=[("Supported files", "*.pdf *.pptx *.zip"), ("PDF files", "*.pdf"), ("PowerPoint slides", "*.pptx"), ("ZIP archives", "*.zip")]))

    def add_zip(self):
        self.add(filedialog.askopenfilenames(title="Add ZIP archives", filetypes=[("ZIP archives", "*.zip")]))

    def add_folder(self):
        folder = filedialog.askdirectory(title="Open a folder containing PDFs or PowerPoint slides")
        if folder:
            self.debug.logger.info("Opening folder: %s", folder)
            try:
                self.add(sorted((p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in (".pdf", ".pptx")), key=lambda p: p.name.casefold()))
            except OSError as error:
                self.debug.logger.exception("Could not read folder: %s", folder)
                messagebox.showerror("Cannot open folder", str(error))

    def queue_previews(self, paths):
        added = self.library.add(paths)
        for item in added:
            self.debug.logger.info("Loading document: %s", item.path)
            self.pending.append((item, self.executor.submit(self.converter.prepare, item.path)))
        return added

    def add(self, paths):
        if self.busy:
            return
        paths = [Path(path).resolve() for path in paths]
        self.queue_previews(path for path in paths if path.suffix.lower() in (".pdf", ".pptx"))
        known = {item.archive for item in self.library.items if item.archive}
        known.update(path for path, _ in self.imports)
        for path in paths:
            if path.suffix.lower() == ".zip" and path not in known:
                self.debug.logger.info("Importing ZIP: %s", path)
                self.imports.append((path, self.executor.submit(self.archives.extract, path)))
                known.add(path)
        self.render()

    def poll_previews(self):
        changed = False
        for path, future in list(self.imports):
            if not future.done():
                continue
            self.imports.remove((path, future))
            try:
                imported = future.result()
                for entry in imported:
                    for item in self.queue_previews([entry.path]):
                        item.display_name, item.origin, item.archive = entry.name, entry.source, entry.archive
                self.notice.set(f"{path.name}: added {len(imported)} document(s). Other file types were skipped.")
                self.debug.logger.info("ZIP imported: %s (%d documents)", path.name, len(imported))
            except Exception as error:
                self.debug.logger.exception("ZIP import failed: %s", path)
                self.notice.set(f"Could not import {path.name}. Your existing files are unchanged.")
                messagebox.showerror("Could not import ZIP", str(error))
            changed = True
        for item, future in list(self.pending):
            if not future.done():
                continue
            self.pending.remove((item, future))
            if item not in self.library.items:
                continue
            try:
                item.pdf_path, item.size, item.pages, item.preview = future.result()
                self.debug.logger.info("Document ready: %s (%d pages)", item.name, item.pages)
                item.ready = True
            except Exception as error:
                item.error = str(error) or "Cannot read this document."
                self.debug.logger.exception("Document preparation failed: %s", item.name)
            changed = True
        if changed:
            self.render()
        self.preview_job = self.root.after(80, self.poll_previews)

    def resize(self, event):
        columns = max(1, int(event.width / self.content._get_widget_scaling()) // 240)
        if columns != self.columns:
            self.columns = columns
            if self.resize_job:
                self.root.after_cancel(self.resize_job)
            self.resize_job = self.root.after(80, self.render)

    def summary(self):
        chosen = self.library.chosen
        loading = sum(not item.ready and not item.error for item in self.library.items)
        errors = sum(bool(item.error) for item in self.library.items)
        self.count_label.configure(text=f"Your library  /  {len(self.library.items)}")
        self.selection_label.configure(text=f"{len(chosen)} file{'s' if len(chosen) != 1 else ''} picked" if chosen else "Ready when you are")
        text = f"{sum(item.pages for item in chosen)} pages  /  {format_size(sum(item.size for item in chosen))}"
        if self.busy:
            text = "Making your PDF..."
        elif self.imports:
            text = f"Unpacking {len(self.imports)} ZIP(s)..."
        elif loading:
            text += f"  /  {loading} loading"
        elif errors:
            text += f"  /  {errors} unreadable"
        self.status.set(text)
        self.merge_button.configure(state="disabled" if self.busy or not chosen else "normal")
        if self.busy or self.imports or loading:
            self.progress.grid()
            self.progress.start()
        else:
            self.progress.stop()
            self.progress.grid_remove()

    def render(self):
        if self.closed:
            return
        if self.resize_job:
            self.root.after_cancel(self.resize_job)
            self.resize_job = None
        offset = self.canvas.yview()[0]
        for child in self.content.winfo_children():
            detach_images(child)
            child.destroy()
        self.controls = [control for control in self.controls if control.winfo_exists()]
        for column in range(max(self.content.grid_size()[0], self.columns, 1) + 1):
            self.content.columnconfigure(column, weight=0, uniform="")
        self.layout_switch.set(self.view.get().title())
        if not self.library.items:
            self.content.columnconfigure(0, weight=1)
            empty = ctk.CTkFrame(self.content, fg_color=SURFACE, corner_radius=24, border_width=1, border_color=BORDER)
            empty.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
            self.text(empty, "", image=empty_art()).pack(pady=(32, 4))
            self.text(empty, "Meet your next perfectly ordered PDF.", 20, True).pack(pady=(0, 6))
            self.text(empty, "Bring PDFs, PowerPoint slides, or a ZIP full of them.\nWe'll help you put the pieces together.", 13, color=MUTED, justify="center").pack()
            self.button(empty, "Add your first files", self.add_files, BLUE, icon("plus"), width=182,
                        text_color="white", hover_color="#185ABC").pack(pady=(20, 32))
        else:
            grid = self.view.get() == "grid"
            columns = max(self.columns, 1) if grid else 1
            for column in range(columns):
                self.content.columnconfigure(column, weight=1, uniform="cards")
            for index, item in enumerate(self.library.items):
                self.card(item, grid).grid(row=index // columns, column=index % columns, sticky="nsew", padx=6, pady=6)
        self.summary()
        self.content.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.canvas.yview_moveto(offset)

    def photo(self, item, grid):
        key = (item.path, grid)
        if key not in self.photos:
            image = item.preview.copy()
            image.thumbnail((144, 146) if grid else (54, 66), Image.Resampling.LANCZOS)
            self.photos[key] = ctk.CTkImage(image, image, size=image.size)
        return self.photos[key]

    def card(self, item, grid):
        checked = item in self.library.chosen
        position = self.library.chosen.index(item) + 1 if checked else None
        card = ctk.CTkFrame(self.content, fg_color=("#F7FAFF", "#1E2D43") if checked else SURFACE,
                            corner_radius=18, border_color=BLUE if item is self.active else BORDER,
                            border_width=2 if item is self.active else 1)
        card.pdf_item = item
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(row=0, column=0 if grid else 2, sticky="ew", padx=14, pady=(12, 6))
        self.text(header, ("ZIP / " if item.archive else "") + item.path.suffix[1:].upper(), 10, True, ("#A1241C", "#F28B82"),
                  fg_color=("#FCE8E6", "#432B34"), corner_radius=6, width=78 if item.archive else 46, height=23).pack(side="left")
        pick = ctk.CTkButton(header, text=str(position) if checked else "Pick", command=lambda: self.toggle(item),
                            image=icon("check", "white", 14) if checked else icon("circle", MUTED, 16),
                            width=58, height=30, corner_radius=15, fg_color=BLUE if checked else SOFT,
                            hover_color="#185ABC" if checked else BORDER, text_color="white" if checked else MUTED,
                            font=(self.font, 12, "bold"))
        pick.pack(side="right", padx=(10, 0))
        card.selection_button = pick
        card.merge_position = position
        if self.busy or not item.ready or item.error:
            pick.configure(state="disabled")
        preview = ctk.CTkFrame(card, fg_color=SOFT, corner_radius=12, height=166 if grid else 80, width=90)
        preview.grid(row=1 if grid else 0, column=0, rowspan=1 if grid else 2, sticky="nsew", padx=14, pady=6 if grid else 14)
        preview.grid_propagate(False)
        preview.grid_rowconfigure(0, weight=1)
        preview.grid_columnconfigure(0, weight=1)
        self.text(preview, "" if item.preview else "PDF" if item.error else "Loading...", size=12,
                  image=self.photo(item, grid) if item.preview else None, color=MUTED).grid(row=0, column=0, pady=10)
        details = ctk.CTkFrame(card, fg_color="transparent")
        details.grid(row=2 if grid else 0, column=0 if grid else 1, rowspan=1 if grid else 2, sticky="nsew", padx=16 if grid else (4, 0), pady=(8, 14) if grid else 16)
        card.columnconfigure(0 if grid else 1, weight=1)
        self.text(details, item.name, 13, True, height=22, wraplength=190 if grid else 320, justify="left", anchor="w").pack(fill="x")
        unit = "slide" if item.path.suffix.lower() == ".pptx" else "page"
        metadata = f"{item.pages} {unit}{'s' if item.pages != 1 else ''}  /  {format_size(item.size)}" if item.ready else "Converting slides..." if item.path.suffix.lower() == ".pptx" else "Reading your PDF..."
        self.text(details, metadata if not item.error else "Can't include this file", 11, height=18, color=MUTED if not item.error else ("#B3261E", "#F28B82"), anchor="w").pack(fill="x", pady=(4, 0))
        if item.error:
            self.text(details, item.error, 11, color=("#B3261E", "#F28B82"), wraplength=190 if grid else 320, justify="left").pack(anchor="w", pady=(4, 0))
        elif item.origin:
            self.text(details, item.origin, 10, height=16, color=MUTED, wraplength=190 if grid else 320, justify="left", anchor="w").pack(fill="x", pady=(6, 0))
        elif not grid:
            self.text(details, str(item.path.parent), 10, height=16, color=MUTED, wraplength=320, justify="left", anchor="w").pack(fill="x", pady=(6, 0))
        self.bind_card(card, item, pick)
        return card

    def bind_card(self, widget, item, pick):
        if widget is pick:
            return
        widget.bind("<ButtonPress-1>", lambda event: self.press(event, item))
        widget.bind("<ButtonRelease-1>", self.release)
        for child in widget.winfo_children():
            self.bind_card(child, item, pick)

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
        if not self.busy:
            self.library.select_all()
            self.render()

    def deselect_all(self):
        if not self.busy:
            self.library.chosen.clear()
            self.render()

    def move(self, delta):
        if not self.busy:
            self.library.move(self.active, delta)
            self.render()

    def remove(self):
        if self.active and not self.busy:
            item = self.active
            self.library.remove(item)
            for grid in (True, False):
                self.photos.pop((item.path, grid), None)
            self.active = None
            self.render()

    def clear(self):
        if self.busy:
            return
        for _, future in self.pending + self.imports:
            future.cancel()
        self.pending.clear()
        self.imports.clear()
        self.library = Library()
        self.active = None
        self.photos.clear()
        self.notice.set("Fresh workspace. Bring something good together.")
        self.debug.logger.debug("Workspace cleared")
        self.render()

    def set_busy(self, busy):
        self.busy = busy
        for control in self.controls:
            if control.winfo_exists():
                control.configure(state="disabled" if busy else "normal")
        self.render()

    def save(self):
        paths = self.library.merge_paths()
        if self.busy or not paths:
            return
        target = filedialog.asksaveasfilename(title="Save your merged PDF", defaultextension=".pdf", initialfile="merged.pdf", filetypes=[("PDF files", "*.pdf")])
        if not target:
            return
        protected = {item.path.resolve() for item in self.library.items}
        protected.update(item.archive.resolve() for item in self.library.items if item.archive)
        if Path(target).resolve() in protected:
            self.debug.logger.warning("Blocked overwriting a source document: %s", target)
            messagebox.showerror("Choose a different destination", "Source PDFs, presentations, and ZIPs cannot be overwritten. Choose a new filename or location.")
            return
        self.debug.logger.info("Merging %d document(s) to %s", len(paths), target)
        for index, item in enumerate(self.library.chosen, 1):
            self.debug.logger.info("  %d. %s (%d pages)", index, item.name, item.pages)
        self.set_busy(True)
        future = self.executor.submit(merge_pdfs, paths, target)
        self.root.after(80, self.poll_merge, future, target)

    def poll_merge(self, future, target):
        if not future.done():
            self.root.after(80, self.poll_merge, future, target)
            return
        self.set_busy(False)
        try:
            future.result()
        except Exception as error:
            self.debug.logger.exception("PDF merge failed")
            self.notice.set("That merge didn't work. Your original files are safe.")
            messagebox.showerror("Could not merge PDFs", str(error))
        else:
            self.debug.logger.info("Merge saved: %s", target)
            self.notice.set(f"All together now. Saved to {target}")
            messagebox.showinfo("Your PDF is ready", f"Merged PDF saved to:\n{target}")

    def close(self):
        if self.closed:
            return
        if self.busy:
            messagebox.showinfo("Merge in progress", "Please wait for the merge to finish before closing.")
            return
        self.closed = True
        self.root.after_cancel(self.preview_job)
        self.root.after_cancel(self.collect_job)
        if self.resize_job:
            self.root.after_cancel(self.resize_job)
        for _, future in self.pending + self.imports:
            future.cancel()
        # Cleanup is queued after any active file read/extraction, including on Windows.
        self.cleanup_future = self.executor.submit(self.archives.close)
        self.executor.shutdown(wait=True)
        self.progress.stop()
        detach_images(self.root)
        self.photos.clear()
        icon.cache_clear()
        gc.collect()
        self.root.destroy()
        self.debug.close()
        if self.gc_was_enabled:
            gc.enable()


if __name__ == "__main__":
    debug = DebugLog()
    try:
        App(ctk.CTk(), debug_log=debug).root.mainloop()
    except Exception:
        debug.logger.exception("Application startup failed")
        messagebox.showerror("Earl Gray could not start", f"See the startup log:\n{debug.path}")
        raise
    finally:
        debug.close()
