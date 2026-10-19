# Earl Gray

A lightweight desktop app that combines PDFs in the order you choose. Built with Python, Tkinter/ttk, pypdf, and PDFium for first-page previews. Files stay on your computer; no accounts, servers, or uploads.

## Windows quick start

Install Python 3.10 or newer from python.org with **Tcl/Tk and IDLE** enabled (the default). In a terminal in this folder:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

Use **Add PDFs** to select multiple files, or **Open folder** to import PDFs directly inside a folder (not subfolders). Folder imports are sorted by filename. Other file types and duplicate paths are ignored. Switch between **Grid** and **List** to see first-page thumbnails, filenames, file sizes, and page counts. Tick the PDFs you want to include: **Merge #1**, **Merge #2**, and so on show the exact output order. Files start unchecked; each tick appends a file to the queue. Unticking removes it and compacts the numbers. Switching views preserves your choices.

Click a card and use **Move earlier / Move later**, or drag a checked card onto another checked card, to change the numbered merge order. The library stays in import order, so you can find files easily while the badges show the merge order. **Select all** appends readable, loaded PDFs in library order; **Deselect all** resets the selection. Remove unwanted files, then choose **Merge & save...**. The native Save As dialog lets you choose the output name and location and confirms overwriting an existing file.

Previews load in the background. Locked, empty, and unreadable PDFs display an error and cannot be selected. Merging runs in a background thread so the window stays responsive. Source files cannot be overwritten. Failed merges preserve existing output. Password-protected PDFs must be unlocked with another tool first; damaged PDFs produce an error dialog.

## Download the Windows app

After a push to `main`, the **Windows app** workflow tests the app and builds an executable on Windows. Open this repository’s **Actions** tab, choose the latest successful **Windows app** run, and download **EarlGray-Windows** under **Artifacts** (GitHub sign-in is required). Extract the ZIP, then double-click `EarlGray.exe`. Build status is visible in Actions; a committed workflow alone does not mean a build has passed.

## Build a Windows executable locally

Build on Windows, using the same virtual environment:

```powershell
.venv\Scripts\python -m pip install pyinstaller==6.16.0
.venv\Scripts\python -m PyInstaller --noconfirm --clean --onefile --windowed --collect-all pypdfium2 --name EarlGray app.py
```

The result is `dist\EarlGray.exe`. Recipients do not need Python. The executable is unsigned; Windows may display a reputation warning. A Windows build must be tested on Windows before distribution.

## Views

Grid view with numbered checkboxes:

![Grid view](docs/grid.png)

List view with the same selection and merge order:

![List view](docs/list.png)

## Development

On Linux/macOS, use `python3 -m venv .venv`, `.venv/bin/python -m pip install -r requirements.txt`, and `.venv/bin/python app.py`. Linux may require the distribution's `python3-tk` package and a desktop display.

Run the merge tests:

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
```

On Linux/macOS use `.venv/bin/python -m unittest discover -s tests -v`.

The test suite covers actual merges, metadata and thumbnail rendering, selection order, and the desktop Save flow. Desktop tests require a display (or Xvfb on Linux) and report skips when no display is available. Windows GUI behavior is also exercised in the Windows workflow.
