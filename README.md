# Earl Gray

A lightweight desktop app that combines PDFs in the order you choose. Built with Python, Tkinter/ttk, and pypdf. Files stay on your computer; no accounts, servers, or uploads.

## Windows quick start

Install Python 3.10 or newer from python.org with **Tcl/Tk and IDLE** enabled (the default). In a terminal in this folder:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

Use **Add PDFs** to select multiple files, or **Open folder** to import PDFs directly inside a folder (not subfolders). Folder imports are sorted by filename. Other file types and duplicate paths are ignored. Drag rows or use **Move up / Move down**, remove unwanted entries, then choose **Merge & save…**. The native Save As dialog lets you choose the output name and location and confirms overwriting an existing file.

Merging runs in a background thread so the window stays responsive. Source files cannot be overwritten. Failed merges preserve existing output. Password-protected PDFs must be unlocked with another tool first; damaged PDFs produce an error dialog.

## Optional Windows executable

Build on Windows, using the same virtual environment:

```powershell
.venv\Scripts\python -m pip install pyinstaller
.venv\Scripts\python -m PyInstaller --noconfirm --clean --onefile --windowed --name EarlGray app.py
```

The result is `dist\EarlGray.exe`. Recipients do not need Python. The executable is unsigned; Windows may display a reputation warning. A Windows build must be tested on Windows before distribution.

## Development

On Linux/macOS, use `python3 -m venv .venv`, `.venv/bin/python -m pip install -r requirements.txt`, and `.venv/bin/python app.py`. Linux may require the distribution's `python3-tk` package and a desktop display.

Run the merge tests:

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
```

On Linux/macOS use `.venv/bin/python -m unittest discover -s tests -v`.
