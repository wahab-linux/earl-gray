"""PDF merging independent of the desktop interface."""
from pathlib import Path
import os
import tempfile

from pypdf import PdfReader, PdfWriter


def merge_pdfs(paths, destination):
    """Merge in input order, replacing the destination only after success."""
    sources = [Path(path) for path in paths]
    target = Path(destination)
    if not sources:
        raise ValueError("Select at least one PDF first.")
    if any(source.resolve() == target.resolve() for source in sources):
        raise ValueError("Choose a destination different from the source PDFs.")
    writer = PdfWriter()
    temporary = None
    try:
        for source in sources:
            if source.suffix.lower() != ".pdf":
                raise ValueError(f"Not a PDF: {source.name}")
            reader = PdfReader(source)
            if reader.is_encrypted:
                raise ValueError(f"Unlock the password-protected PDF first: {source.name}")
            writer.append(reader)
        if not len(writer.pages):
            raise ValueError("The selected PDFs contain no pages.")
        with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".pdf", delete=False) as output:
            temporary = Path(output.name)
            writer.write(output)
        os.replace(temporary, target)
        temporary = None
    finally:
        writer.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)
