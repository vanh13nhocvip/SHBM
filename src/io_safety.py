"""I/O safety helpers to prevent accidental modification of source PDFs.

Provide small runtime guards that raise an exception if code attempts to
write to a path that looks like an original PDF. This helps ensure the
application never overwrites or alters the user's source PDF files.
"""
from pathlib import Path


class IOErrorSafety(Exception):
    pass


def assert_not_pdf_target(path: str) -> None:
    """Raise if `path` points to a .pdf file (case-insensitive).

    Use this before opening files for writing to make sure the program
    is not about to overwrite a PDF file by mistake.
    """
    if not path:
        return
    p = Path(path)
    if p.suffix.lower() == '.pdf':
        raise IOErrorSafety(f'Attempt to write to PDF file prevented: {path}')
