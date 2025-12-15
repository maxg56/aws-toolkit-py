"""Data models for Textract results."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextractLine:
    """Represents a line of text extracted from a document."""

    text: str
    confidence: float
    bounding_box: dict[str, float]  # {top, left, width, height}


@dataclass
class TextractTable:
    """Represents a table extracted from a document."""

    rows: int
    columns: int
    cells: list[list[str]]  # Matrix: rows x columns
    confidence: float


@dataclass
class TextractPage:
    """Represents a page in the extracted document."""

    page_number: int
    width: float
    height: float
    lines: list[TextractLine]
    tables: list[TextractTable]
    raw_text: str  # All text from this page concatenated


@dataclass
class TextractDocument:
    """
    Structured document result from Textract.

    This is the main output format - clean, serializable JSON structure.
    No AWS Blocks exposed.
    """

    pages: list[TextractPage]
    full_text: str  # All text concatenated across all pages
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "pages": [
                {
                    "page_number": page.page_number,
                    "width": page.width,
                    "height": page.height,
                    "lines": [
                        {
                            "text": line.text,
                            "confidence": line.confidence,
                            "bounding_box": line.bounding_box,
                        }
                        for line in page.lines
                    ],
                    "tables": [
                        {
                            "rows": table.rows,
                            "columns": table.columns,
                            "cells": table.cells,
                            "confidence": table.confidence,
                        }
                        for table in page.tables
                    ],
                    "raw_text": page.raw_text,
                }
                for page in self.pages
            ],
            "full_text": self.full_text,
            "metadata": self.metadata,
        }
