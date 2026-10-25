"""Extract text from a PDF page by page using PyMuPDF."""
import pymupdf  # PyMuPDF (needs version 1.24.3 or newer)

from .exceptions import InvalidPDFError


def extract_pages(path):
    """Return a list of (page_number, raw_text). Page numbers start at 1."""
    try:
        doc = pymupdf.open(str(path))
    except Exception as exc:
        raise InvalidPDFError() from exc
    try:
        if doc.needs_pass:
            raise InvalidPDFError("This PDF is password-protected. Remove the password and upload it again.")
        pages = []
        for index, page in enumerate(doc, start=1):
            pages.append((index, page.get_text("text")))
        return pages
    except InvalidPDFError:
        raise
    except Exception as exc:
        raise InvalidPDFError() from exc
    finally:
        doc.close()
