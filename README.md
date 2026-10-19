# Earl Gray

A little order. One perfect PDF.

A lightweight Python desktop app with rounded cards, Google-inspired colors, real PDF previews, and light/dark mode. Import PDFs, folders, or ZIPs, pick the order, and save one combined PDF. Everything stays on your computer.

![Light mode](docs/grid.png)

## Run on Windows

Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/windows/), with **Add Python to PATH** checked and **Tcl/Tk** included (the default). Close and reopen Command Prompt after installation.

Open the downloaded project folder in File Explorer, type `cmd` in its address bar, and press Enter. Run:

```bat
python -m pip install -r requirements.txt
python app.py
```

If your installation uses `py` instead of `python`, use `py` in both commands. Run these commands in the folder containing `app.py` and `requirements.txt`.

## Download without installing Python

After a push to `main`, the **Windows app** workflow tests the app and builds an executable on Windows. Open this repository's **Actions** tab, choose the latest successful **Windows app** run, and download **EarlGray-Windows** under **Artifacts** (GitHub sign-in required). Extract the ZIP and double-click `EarlGray.exe`.

The workflow must finish successfully before its download is available. The executable is unsigned; Windows may display a reputation warning.

## Make a PDF

1. **Add PDFs**, **Add ZIP**, or **Open folder**. Folder import includes PDFs directly inside the folder. ZIP import also finds PDFs inside nested folders; other file types are skipped.
2. Switch between **Grid** and **List**. Both show first-page thumbnails, filenames, page counts, and sizes. Imported ZIP files also show their archive and subfolder.
3. Click **Pick** on each PDF you want. The checkmark and number show the exact merge order. Picking another PDF appends it; unpicking closes the gap. **Select all** appends all readable, loaded PDFs in library order.
4. Click a card to focus it, then use the up/down arrows to move it earlier/later. You can also drag a picked card onto another picked card. The library stays in import order while the numbers show output order.
5. Click **Merge & save**, choose a name and location in the native Save As dialog, and save. Existing destinations require overwrite confirmation. Source PDFs cannot be overwritten.

The circular moon/sun button switches the entire interface between **Light** and **Dark**. Your selection and merge order stay intact when switching themes or views.

The red trash button removes the focused card; **Clear workspace** removes all cards. Locked, empty, and unreadable PDFs show an error and cannot be picked. Unlock password-protected PDFs and ZIPs with another tool before importing them.

## ZIP import

ZIPs are unpacked in the background into app-owned temporary storage, leaving the original archive unchanged. Original PDF names are displayed even when several subfolders contain the same filename. Imported PDFs remain available for the session; temporary storage is removed when the app closes. Re-adding the same archive does not duplicate its PDFs while they remain in the library. Nested ZIP archives are skipped.

Each ZIP can contain up to 2,000 PDFs, with a maximum of 256 MB per PDF and 512 MB of extracted PDF data in total. Unsafe paths and PDF symlinks are rejected. Corrupt archives fail without changing your existing library.

## Dark mode

![Dark mode](docs/dark.png)

## List view

![List view](docs/list.png)

## Build a Windows executable

Build on Windows:

```bat
python -m pip install -r requirements.txt pyinstaller==6.16.0
python -m PyInstaller --noconfirm --clean --onefile --windowed --collect-all pypdfium2 --collect-all customtkinter --hidden-import PIL._tkinter_finder --name EarlGray app.py
```

The result is `dist\EarlGray.exe`. `--collect-all customtkinter` includes the theme and font resources needed by the rounded interface. Recipients do not need Python. Test a Windows build on Windows before distribution.

## Development

Built with CustomTkinter, Pillow, pypdf, and PDFium. ZIP support uses Python's standard library. PDF inspection, rendering, extraction, and merging run on one background worker; the UI remains responsive. Failed merges preserve existing output. Tk images and cyclic garbage collection are cleaned up on the UI thread.

For an isolated environment:

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
.venv\Scripts\python -m unittest discover -s tests -v
```

On Linux/macOS, create the environment with `python3 -m venv .venv` and use `.venv/bin/python` for installation, running, and testing. Linux requires a Tk-enabled Python and a desktop display; the distribution's `python3-tk` package may be needed.

The tests cover actual merges, preview rendering, numbered selection, themes, view switching, ZIP import, extraction limits, unsafe paths, cleanup, and saving through the desktop UI. Desktop tests require a display or Xvfb and explicitly report a skip when no display exists. The Windows workflow runs the same suite before packaging, then checks that the packaged app opens and closes from outside the checkout before uploading the executable.
