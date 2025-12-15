"""Data models for aws-simple."""

from .textract import TextractDocument, TextractLine, TextractPage, TextractTable

__all__ = [
    "TextractDocument",
    "TextractLine",
    "TextractPage",
    "TextractTable",
]
