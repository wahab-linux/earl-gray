"""Persistent, inline import screen; only labels and progress values change."""
import time
import customtkinter as ctk
from tkinter import ttk


class LoadingScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=("#FFFFFF", "#1B2230"), corner_radius=22,
                         border_width=1, border_color=("#E1E7F1", "#303C50"))
        self.app = app
        self.rows = {}
        self.started = 0
        self.last_second = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)
        app.text(self, "Preparing your files", 23, True).grid(row=0, column=0, sticky="w", padx=24, pady=(24, 4))
        self.stage = app.text(self, "Discovering documents", 14, True, ("#1967D2", "#8AB4F8"))
        self.stage.grid(row=1, column=0, sticky="w", padx=24, pady=(0, 4))
        self.detail = app.text(self, "", 12, color=("#647189", "#A3B0C6"), anchor="w", wraplength=720)
        self.detail.grid(row=2, column=0, sticky="ew", padx=24)
        self.bar = ctk.CTkProgressBar(self, height=8, corner_radius=4, mode="determinate", progress_color="#1967D2")
        self.bar.grid(row=3, column=0, sticky="ew", padx=24, pady=(16, 12))
        table = ctk.CTkFrame(self, fg_color="transparent")
        table.grid(row=4, column=0, sticky="nsew", padx=24)
        table.grid_rowconfigure(0, weight=1)
        table.grid_columnconfigure(0, weight=1)
        self.files = ttk.Treeview(table, columns=("name", "state"), show="headings", style="Import.Treeview", selectmode="none")
        self.files.heading("name", text="File")
        self.files.heading("state", text="Preparation")
        self.files.column("name", width=270, minwidth=140)
        self.files.column("state", width=390, minwidth=180)
        self.files.grid(row=0, column=0, sticky="nsew")
        scrollbar = ctk.CTkScrollbar(table, command=self.files.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.files.configure(yscrollcommand=scrollbar.set)
        self.apply_theme()
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=5, column=0, sticky="ew", padx=24, pady=18)
        self.count = app.text(bottom, "Discovering files", 12, True)
        self.count.pack(side="left")
        self.elapsed = app.text(bottom, "0s", 11, color=("#647189", "#A3B0C6"))
        self.elapsed.pack(side="left", padx=12)
        self.cancel_button = ctk.CTkButton(bottom, text="Cancel remaining", width=136, height=34, corner_radius=11,
                                          fg_color=("#EBF0F8", "#252F40"), text_color=("#202B40", "#EDF2FC"),
                                          command=app.cancel_import, font=(app.font, 12))
        self.cancel_button.pack(side="right")

    def start(self):
        self.files.delete(*self.files.get_children())
        self.rows.clear()
        self.started = time.monotonic()
        self.last_second = None
        self.stage.configure(text="Discovering documents")
        self.detail.configure(text="Checking selected files and unpacking archives. Merge unlocks when preparation finishes.")
        self.count.configure(text="Discovering files")
        self.bar.set(0)
        self.cancel_button.configure(state="normal", text="Cancel remaining")

    def apply_theme(self):
        dark = self.app.mode == "dark"
        background, foreground = ("#1B2230", "#EDF2FC") if dark else ("#FFFFFF", "#202B40")
        heading = "#252F40" if dark else "#EBF0F8"
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Import.Treeview", background=background, fieldbackground=background,
                        foreground=foreground, rowheight=34, borderwidth=0, font=(self.app.font, 11))
        style.configure("Import.Treeview.Heading", background=heading, foreground=foreground,
                        font=(self.app.font, 11, "bold"), padding=(8, 8))

    def row(self, key, name, state):
        if key not in self.rows:
            self.rows[key] = self.files.insert("", "end", values=(name, state))
        else:
            self.files.item(self.rows[key], values=(name, state))

    def tick(self):
        seconds = int(time.monotonic() - self.started)
        if seconds != self.last_second:
            self.last_second = seconds
            self.elapsed.configure(text=f"{seconds}s elapsed")
