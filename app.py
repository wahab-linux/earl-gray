"""Earl Gray: a small, local PDF merger for Windows and other desktops."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from pdf_merge import merge_pdfs


class App:
    def __init__(self, root):
        self.root = root
        self.paths = []
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.busy = False
        self.drag_index = None
        root.title("Earl Gray · PDF merger")
        root.geometry("760x540")
        root.minsize(600, 420)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 11), background="#f6f7fb", foreground="#202938")
        style.configure("TButton", padding=(12, 8))
        style.configure("Title.TLabel", font=("Segoe UI", 24, "bold"))
        frame = ttk.Frame(root, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Earl Gray", style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Your PDFs, in the right order. All processing stays on your device.").pack(anchor="w", pady=(4, 18))
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x")
        self.buttons = []
        self.button(toolbar, "Add PDFs", self.add_files).pack(side="left")
        self.button(toolbar, "Open folder", self.add_folder).pack(side="left", padx=8)
        ttk.Label(frame, text="Drag rows or use Move up / Move down to set the page order.").pack(anchor="w", pady=(16, 8))
        table_frame = ttk.Frame(frame)
        table_frame.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table_frame, columns=("name", "folder"), show="headings", selectmode="browse")
        self.table.heading("name", text="PDF file")
        self.table.heading("folder", text="Folder")
        self.table.column("name", width=240)
        self.table.column("folder", width=360)
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.table.bind("<ButtonPress-1>", self.drag_start)
        self.table.bind("<B1-Motion>", self.drag_move)
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=12)
        self.button(actions, "Move up", lambda: self.move(-1)).pack(side="left")
        self.button(actions, "Move down", lambda: self.move(1)).pack(side="left", padx=6)
        self.button(actions, "Remove", self.remove).pack(side="left")
        self.button(actions, "Clear", self.clear).pack(side="left", padx=6)
        self.button(actions, "Merge & save…", self.save).pack(side="right")
        self.status = tk.StringVar(value="Add PDFs or open a folder to get started.")
        ttk.Label(frame, textvariable=self.status).pack(anchor="w")
        root.protocol("WM_DELETE_WINDOW", self.close)

    def button(self, parent, text, command):
        button = ttk.Button(parent, text=text, command=command)
        self.buttons.append(button)
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
        for path in paths:
            path = Path(path).resolve()
            if path.suffix.lower() == ".pdf" and path not in self.paths:
                self.paths.append(path)
        self.refresh()

    def refresh(self, selected=None):
        self.table.delete(*self.table.get_children())
        for index, path in enumerate(self.paths):
            self.table.insert("", "end", iid=str(index), values=(path.name, str(path.parent)))
        if selected is not None and self.paths:
            item = str(min(selected, len(self.paths) - 1))
            self.table.selection_set(item)
            self.table.see(item)
        self.status.set(f"{len(self.paths)} PDF(s) · merge follows the order above")

    def selected(self):
        selection = self.table.selection()
        return int(selection[0]) if selection else None

    def move(self, delta):
        index = self.selected()
        if index is not None and 0 <= index + delta < len(self.paths):
            self.paths[index], self.paths[index + delta] = self.paths[index + delta], self.paths[index]
            self.refresh(index + delta)

    def drag_start(self, event):
        item = self.table.identify_row(event.y)
        self.drag_index = int(item) if item else None

    def drag_move(self, event):
        if self.busy or self.drag_index is None:
            return
        item = self.table.identify_row(event.y)
        if item:
            destination = int(item)
            self.paths.insert(destination, self.paths.pop(self.drag_index))
            self.drag_index = destination
            self.refresh(destination)

    def remove(self):
        index = self.selected()
        if index is not None:
            self.paths.pop(index)
            self.refresh(index)

    def clear(self):
        self.paths.clear()
        self.refresh()

    def save(self):
        if not self.paths:
            messagebox.showinfo("Add PDFs", "Select at least one PDF first.")
            return
        target = filedialog.asksaveasfilename(title="Save merged PDF", defaultextension=".pdf", initialfile="merged.pdf", filetypes=[("PDF files", "*.pdf")])
        if not target:
            return
        self.busy = True
        for button in self.buttons:
            button.state(["disabled"])
        self.status.set("Merging PDFs…")
        future = self.executor.submit(merge_pdfs, list(self.paths), target)
        self.root.after(100, self.poll, future, target)

    def poll(self, future, target):
        if not future.done():
            self.root.after(100, self.poll, future, target)
            return
        self.busy = False
        for button in self.buttons:
            button.state(["!disabled"])
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
        self.executor.shutdown(wait=False)
        self.root.destroy()


if __name__ == "__main__":
    App(tk.Tk()).root.mainloop()
