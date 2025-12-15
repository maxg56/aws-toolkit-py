"""Parser to transform AWS Textract Blocks into clean JSON structure."""

from typing import Any

from ..models.textract import (
    TextractDocument,
    TextractLine,
    TextractPage,
    TextractTable,
)


class TextractParser:
    """Transforms AWS Textract response into clean, structured format."""

    @staticmethod
    def parse_response(response: dict[str, Any]) -> TextractDocument:
        """
        Parse Textract API response into TextractDocument.

        Args:
            response: Raw AWS Textract response with Blocks

        Returns:
            TextractDocument with structured data
        """
        blocks = response.get("Blocks", [])

        # Build block lookup
        block_map = {block["Id"]: block for block in blocks}

        # Group blocks by page
        pages_data: dict[int, dict[str, Any]] = {}

        for block in blocks:
            block_type = block.get("BlockType")
            page_num = block.get("Page", 1)

            if page_num not in pages_data:
                pages_data[page_num] = {
                    "lines": [],
                    "tables": [],
                    "page_geometry": block.get("Geometry", {}),
                }

            if block_type == "LINE":
                pages_data[page_num]["lines"].append(block)
            elif block_type == "TABLE":
                pages_data[page_num]["tables"].append(block)

        # Build pages
        pages: list[TextractPage] = []
        all_text_parts: list[str] = []

        for page_num in sorted(pages_data.keys()):
            page_info = pages_data[page_num]

            # Parse lines
            lines = TextractParser._parse_lines(page_info["lines"])

            # Parse tables
            tables = TextractParser._parse_tables(page_info["tables"], block_map)

            # Get page dimensions
            geometry = page_info["page_geometry"]
            bbox = geometry.get("BoundingBox", {})
            width = bbox.get("Width", 1.0)
            height = bbox.get("Height", 1.0)

            # Concatenate text for this page
            page_text = "\n".join(line.text for line in lines)
            all_text_parts.append(page_text)

            page = TextractPage(
                page_number=page_num,
                width=width,
                height=height,
                lines=lines,
                tables=tables,
                raw_text=page_text,
            )
            pages.append(page)

        full_text = "\n\n".join(all_text_parts)

        return TextractDocument(
            pages=pages,
            full_text=full_text,
            metadata={
                "document_metadata": response.get("DocumentMetadata", {}),
                "total_pages": len(pages),
            },
        )

    @staticmethod
    def _parse_lines(line_blocks: list[dict[str, Any]]) -> list[TextractLine]:
        """Parse LINE blocks into TextractLine objects."""
        lines = []
        for block in line_blocks:
            text = block.get("Text", "")
            confidence = block.get("Confidence", 0.0)
            geometry = block.get("Geometry", {})
            bbox = geometry.get("BoundingBox", {})

            bounding_box = {
                "top": bbox.get("Top", 0.0),
                "left": bbox.get("Left", 0.0),
                "width": bbox.get("Width", 0.0),
                "height": bbox.get("Height", 0.0),
            }

            lines.append(
                TextractLine(
                    text=text,
                    confidence=confidence,
                    bounding_box=bounding_box,
                )
            )
        return lines

    @staticmethod
    def _parse_tables(
        table_blocks: list[dict[str, Any]], block_map: dict[str, dict[str, Any]]
    ) -> list[TextractTable]:
        """Parse TABLE blocks into TextractTable objects."""
        tables = []

        for table_block in table_blocks:
            # Get table dimensions
            relationships = table_block.get("Relationships", [])
            cell_ids = []
            for rel in relationships:
                if rel.get("Type") == "CHILD":
                    cell_ids = rel.get("Ids", [])
                    break

            # Build cell matrix
            cells_data: dict[tuple[int, int], str] = {}
            max_row = 0
            max_col = 0

            for cell_id in cell_ids:
                cell_block = block_map.get(cell_id)
                if not cell_block or cell_block.get("BlockType") != "CELL":
                    continue

                row_index = cell_block.get("RowIndex", 1) - 1
                col_index = cell_block.get("ColumnIndex", 1) - 1
                max_row = max(max_row, row_index)
                max_col = max(max_col, col_index)

                # Get cell text from WORD children
                cell_text = TextractParser._get_cell_text(cell_block, block_map)
                cells_data[(row_index, col_index)] = cell_text

            # Build matrix
            rows = max_row + 1
            cols = max_col + 1
            cell_matrix = [["" for _ in range(cols)] for _ in range(rows)]

            for (row_idx, col_idx), text in cells_data.items():
                cell_matrix[row_idx][col_idx] = text

            tables.append(
                TextractTable(
                    rows=rows,
                    columns=cols,
                    cells=cell_matrix,
                    confidence=table_block.get("Confidence", 0.0),
                )
            )

        return tables

    @staticmethod
    def _get_cell_text(cell_block: dict[str, Any], block_map: dict[str, dict[str, Any]]) -> str:
        """Extract text from a CELL block by following relationships."""
        relationships = cell_block.get("Relationships", [])
        word_ids = []

        for rel in relationships:
            if rel.get("Type") == "CHILD":
                word_ids = rel.get("Ids", [])
                break

        words = []
        for word_id in word_ids:
            word_block = block_map.get(word_id)
            if word_block and word_block.get("BlockType") == "WORD":
                words.append(word_block.get("Text", ""))

        return " ".join(words)
