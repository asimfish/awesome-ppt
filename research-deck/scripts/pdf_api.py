"""PyMuPDF adopted its current module name after our oldest supported release."""

try:
    import pymupdf as fitz
except ImportError:
    import fitz

__all__ = ["fitz"]
