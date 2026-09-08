"""Tests for the internal Textract response parser."""

from typing import Any

from aws_simple._parsers.textract_parser import TextractParser
from aws_simple.models.textract import TextractDocument

# Test data constants
LINE_CONFIDENCE = 98.25
TABLE_CONFIDENCE = 97.5
PAGE_WIDTH = 0.8
PAGE_HEIGHT = 0.6
LINE_BBOX_TOP = 0.11
LINE_BBOX_LEFT = 0.12
LINE_BBOX_WIDTH = 0.13
LINE_BBOX_HEIGHT = 0.14
EXPECTED_TWO = 2
EXPECTED_THREE = 3


def _table_block(table_id: str, cell_ids: list[str], **extra: Any) -> dict[str, Any]:
    """Build a TABLE block referencing the given cell ids."""
    block: dict[str, Any] = {
        "BlockType": "TABLE",
        "Id": table_id,
        "Page": 1,
        "Confidence": TABLE_CONFIDENCE,
        "Relationships": [{"Type": "CHILD", "Ids": cell_ids}],
    }
    block.update(extra)
    return block


def _cell_block(cell_id: str, row: int, col: int, word_ids: list[str]) -> dict[str, Any]:
    """Build a CELL block referencing the given word ids."""
    return {
        "BlockType": "CELL",
        "Id": cell_id,
        "RowIndex": row,
        "ColumnIndex": col,
        "Relationships": [{"Type": "CHILD", "Ids": word_ids}],
    }


def _word_block(word_id: str, text: str) -> dict[str, Any]:
    """Build a WORD block."""
    return {"BlockType": "WORD", "Id": word_id, "Text": text}


# ---------------------------------------------------------------------------
# parse_response
# ---------------------------------------------------------------------------


def test_parse_response_empty_dict() -> None:
    """A response without Blocks yields an empty document, not an error."""
    doc = TextractParser.parse_response({})

    assert isinstance(doc, TextractDocument)
    assert doc.pages == []
    assert doc.full_text == ""
    assert doc.metadata == {"document_metadata": {}, "total_pages": 0}


def test_parse_response_empty_blocks_list() -> None:
    """An explicitly empty Blocks list also yields an empty document."""
    doc = TextractParser.parse_response({"Blocks": [], "DocumentMetadata": {"Pages": 0}})

    assert doc.pages == []
    assert doc.full_text == ""
    assert doc.metadata["document_metadata"] == {"Pages": 0}


def test_parse_response_keeps_document_metadata() -> None:
    """DocumentMetadata is copied verbatim into the parsed metadata."""
    response = {
        "DocumentMetadata": {"Pages": 3},
        "Blocks": [{"BlockType": "LINE", "Id": "l1", "Page": 1, "Text": "Hello"}],
    }

    doc = TextractParser.parse_response(response)

    assert doc.metadata["document_metadata"] == {"Pages": 3}
    assert doc.metadata["total_pages"] == 1


def test_parse_response_sorts_pages_and_joins_text() -> None:
    """Pages are emitted in ascending page order regardless of block order."""
    response = {
        "Blocks": [
            {"BlockType": "LINE", "Id": "l3", "Page": 3, "Text": "third"},
            {"BlockType": "LINE", "Id": "l1", "Page": 1, "Text": "first"},
            {"BlockType": "LINE", "Id": "l2", "Page": 2, "Text": "second"},
        ]
    }

    doc = TextractParser.parse_response(response)

    assert [page.page_number for page in doc.pages] == [1, 2, 3]
    assert doc.full_text == "first\n\nsecond\n\nthird"
    assert doc.metadata["total_pages"] == EXPECTED_THREE


def test_parse_response_joins_lines_within_page_with_newline() -> None:
    """Lines of one page are joined by a single newline in raw_text."""
    response = {
        "Blocks": [
            {"BlockType": "LINE", "Id": "l1", "Page": 1, "Text": "line one"},
            {"BlockType": "LINE", "Id": "l2", "Page": 1, "Text": "line two"},
        ]
    }

    doc = TextractParser.parse_response(response)

    assert len(doc.pages) == 1
    assert doc.pages[0].raw_text == "line one\nline two"
    assert doc.full_text == "line one\nline two"


def test_parse_response_defaults_missing_page_number_to_one() -> None:
    """Blocks without a Page key are attributed to page 1."""
    response = {"Blocks": [{"BlockType": "LINE", "Id": "l1", "Text": "no page key"}]}

    doc = TextractParser.parse_response(response)

    assert len(doc.pages) == 1
    assert doc.pages[0].page_number == 1
    assert doc.pages[0].lines[0].text == "no page key"


def test_parse_response_page_dimensions_from_geometry() -> None:
    """Page width/height come from the first block seen for that page."""
    response = {
        "Blocks": [
            {
                "BlockType": "PAGE",
                "Id": "p1",
                "Page": 1,
                "Geometry": {"BoundingBox": {"Width": PAGE_WIDTH, "Height": PAGE_HEIGHT}},
            },
            {"BlockType": "LINE", "Id": "l1", "Page": 1, "Text": "text"},
        ]
    }

    doc = TextractParser.parse_response(response)

    assert doc.pages[0].width == PAGE_WIDTH
    assert doc.pages[0].height == PAGE_HEIGHT


def test_parse_response_page_dimensions_default_to_one() -> None:
    """A page whose first block has no Geometry falls back to 1.0 x 1.0."""
    response = {"Blocks": [{"BlockType": "LINE", "Id": "l1", "Page": 1, "Text": "text"}]}

    doc = TextractParser.parse_response(response)

    assert doc.pages[0].width == 1.0
    assert doc.pages[0].height == 1.0


def test_parse_response_ignores_non_line_non_table_blocks() -> None:
    """WORD / KEY_VALUE_SET blocks do not become lines or tables."""
    response = {
        "Blocks": [
            {"BlockType": "LINE", "Id": "l1", "Page": 1, "Text": "kept"},
            {"BlockType": "WORD", "Id": "w1", "Page": 1, "Text": "dropped"},
            {"BlockType": "KEY_VALUE_SET", "Id": "kv1", "Page": 1},
            {"BlockType": "SELECTION_ELEMENT", "Id": "s1", "Page": 1},
        ]
    }

    doc = TextractParser.parse_response(response)

    assert [line.text for line in doc.pages[0].lines] == ["kept"]
    assert doc.pages[0].tables == []


def test_parse_response_block_without_block_type() -> None:
    """A block with no BlockType still registers its page but adds no content."""
    response = {"Blocks": [{"Id": "unknown", "Page": 2}]}

    doc = TextractParser.parse_response(response)

    assert len(doc.pages) == 1
    assert doc.pages[0].page_number == EXPECTED_TWO
    assert doc.pages[0].lines == []
    assert doc.pages[0].tables == []
    assert doc.pages[0].raw_text == ""


# ---------------------------------------------------------------------------
# _parse_lines
# ---------------------------------------------------------------------------


def test_parse_lines_reads_text_confidence_and_bounding_box() -> None:
    """Line fields are mapped onto the TextractLine model."""
    blocks = [
        {
            "BlockType": "LINE",
            "Id": "l1",
            "Text": "Total: 42",
            "Confidence": LINE_CONFIDENCE,
            "Geometry": {
                "BoundingBox": {
                    "Top": LINE_BBOX_TOP,
                    "Left": LINE_BBOX_LEFT,
                    "Width": LINE_BBOX_WIDTH,
                    "Height": LINE_BBOX_HEIGHT,
                }
            },
        }
    ]

    lines = TextractParser._parse_lines(blocks)

    assert len(lines) == 1
    assert lines[0].text == "Total: 42"
    assert lines[0].confidence == LINE_CONFIDENCE
    assert lines[0].bounding_box == {
        "top": LINE_BBOX_TOP,
        "left": LINE_BBOX_LEFT,
        "width": LINE_BBOX_WIDTH,
        "height": LINE_BBOX_HEIGHT,
    }


def test_parse_lines_defaults_for_missing_fields() -> None:
    """A LINE block missing Text/Confidence/Geometry gets zeroed defaults."""
    lines = TextractParser._parse_lines([{"BlockType": "LINE", "Id": "l1"}])

    assert lines[0].text == ""
    assert lines[0].confidence == 0.0
    assert lines[0].bounding_box == {"top": 0.0, "left": 0.0, "width": 0.0, "height": 0.0}


def test_parse_lines_partial_bounding_box() -> None:
    """Missing bounding box keys individually default to 0.0."""
    blocks = [
        {
            "BlockType": "LINE",
            "Id": "l1",
            "Text": "partial",
            "Geometry": {"BoundingBox": {"Top": LINE_BBOX_TOP}},
        }
    ]

    lines = TextractParser._parse_lines(blocks)

    assert lines[0].bounding_box == {
        "top": LINE_BBOX_TOP,
        "left": 0.0,
        "width": 0.0,
        "height": 0.0,
    }


def test_parse_lines_empty_input() -> None:
    """No LINE blocks yields no lines."""
    assert TextractParser._parse_lines([]) == []


# ---------------------------------------------------------------------------
# _parse_tables
# ---------------------------------------------------------------------------


def test_parse_tables_builds_cell_matrix() -> None:
    """A 2x2 table is reconstructed as a row-major matrix of cell text."""
    blocks = [
        _table_block("t1", ["c1", "c2", "c3", "c4"]),
        _cell_block("c1", 1, 1, ["w1"]),
        _cell_block("c2", 1, 2, ["w2"]),
        _cell_block("c3", 2, 1, ["w3", "w4"]),
        _cell_block("c4", 2, 2, ["w5"]),
        _word_block("w1", "Item"),
        _word_block("w2", "Price"),
        _word_block("w3", "Product"),
        _word_block("w4", "A"),
        _word_block("w5", "$10"),
    ]
    block_map = {block["Id"]: block for block in blocks}

    tables = TextractParser._parse_tables([blocks[0]], block_map)

    assert len(tables) == 1
    table = tables[0]
    assert table.rows == EXPECTED_TWO
    assert table.columns == EXPECTED_TWO
    assert table.cells == [["Item", "Price"], ["Product A", "$10"]]
    assert table.confidence == TABLE_CONFIDENCE


def test_parse_tables_no_relationships() -> None:
    """A TABLE block with no relationships yields a 1x1 empty matrix."""
    table_block: dict[str, Any] = {"BlockType": "TABLE", "Id": "t1"}

    tables = TextractParser._parse_tables([table_block], {"t1": table_block})

    assert tables[0].rows == 1
    assert tables[0].columns == 1
    assert tables[0].cells == [[""]]
    assert tables[0].confidence == 0.0


def test_parse_tables_only_non_child_relationships() -> None:
    """Relationship types other than CHILD are ignored when collecting cells."""
    table_block: dict[str, Any] = {
        "BlockType": "TABLE",
        "Id": "t1",
        "Relationships": [{"Type": "TABLE_TITLE", "Ids": ["title-1"]}],
    }

    tables = TextractParser._parse_tables([table_block], {"t1": table_block})

    assert tables[0].cells == [[""]]


def test_parse_tables_child_relationship_after_other_types() -> None:
    """The CHILD relationship is found even when it is not the first one."""
    table_block = _table_block("t1", ["c1"])
    table_block["Relationships"] = [
        {"Type": "TABLE_FOOTER", "Ids": ["f1"]},
        {"Type": "CHILD", "Ids": ["c1"]},
    ]
    cell = _cell_block("c1", 1, 1, ["w1"])
    word = _word_block("w1", "Hello")
    block_map = {"t1": table_block, "c1": cell, "w1": word}

    tables = TextractParser._parse_tables([table_block], block_map)

    assert tables[0].cells == [["Hello"]]


def test_parse_tables_skips_unknown_cell_ids() -> None:
    """Cell ids missing from the block map are skipped instead of crashing."""
    table_block = _table_block("t1", ["c1", "ghost-cell"])
    cell = _cell_block("c1", 1, 1, ["w1"])
    word = _word_block("w1", "Only")
    block_map = {"t1": table_block, "c1": cell, "w1": word}

    tables = TextractParser._parse_tables([table_block], block_map)

    assert tables[0].rows == 1
    assert tables[0].columns == 1
    assert tables[0].cells == [["Only"]]


def test_parse_tables_skips_children_that_are_not_cells() -> None:
    """MERGED_CELL and other non-CELL children do not enlarge the matrix."""
    table_block = _table_block("t1", ["m1", "c1"])
    merged = {
        "BlockType": "MERGED_CELL",
        "Id": "m1",
        "RowIndex": 9,
        "ColumnIndex": 9,
    }
    cell = _cell_block("c1", 1, 1, ["w1"])
    word = _word_block("w1", "Value")
    block_map = {"t1": table_block, "m1": merged, "c1": cell, "w1": word}

    tables = TextractParser._parse_tables([table_block], block_map)

    assert tables[0].rows == 1
    assert tables[0].columns == 1
    assert tables[0].cells == [["Value"]]


def test_parse_tables_cell_index_defaults() -> None:
    """A CELL without RowIndex/ColumnIndex lands at position (0, 0)."""
    table_block = _table_block("t1", ["c1"])
    cell: dict[str, Any] = {
        "BlockType": "CELL",
        "Id": "c1",
        "Relationships": [{"Type": "CHILD", "Ids": ["w1"]}],
    }
    word = _word_block("w1", "Default")
    block_map = {"t1": table_block, "c1": cell, "w1": word}

    tables = TextractParser._parse_tables([table_block], block_map)

    assert tables[0].cells == [["Default"]]


def test_parse_tables_sparse_cells_are_padded() -> None:
    """Positions with no CELL block are filled with empty strings."""
    table_block = _table_block("t1", ["c1", "c2"])
    blocks = {
        "t1": table_block,
        "c1": _cell_block("c1", 1, 1, ["w1"]),
        "c2": _cell_block("c2", 3, 3, ["w2"]),
        "w1": _word_block("w1", "TopLeft"),
        "w2": _word_block("w2", "BottomRight"),
    }

    tables = TextractParser._parse_tables([table_block], blocks)

    assert tables[0].rows == EXPECTED_THREE
    assert tables[0].columns == EXPECTED_THREE
    assert tables[0].cells == [
        ["TopLeft", "", ""],
        ["", "", ""],
        ["", "", "BottomRight"],
    ]


def test_parse_tables_multiple_tables() -> None:
    """Several TABLE blocks each produce their own matrix."""
    table_a = _table_block("t1", ["c1"])
    table_b = _table_block("t2", ["c2"])
    block_map = {
        "t1": table_a,
        "t2": table_b,
        "c1": _cell_block("c1", 1, 1, ["w1"]),
        "c2": _cell_block("c2", 1, 1, ["w2"]),
        "w1": _word_block("w1", "A"),
        "w2": _word_block("w2", "B"),
    }

    tables = TextractParser._parse_tables([table_a, table_b], block_map)

    assert len(tables) == EXPECTED_TWO
    assert tables[0].cells == [["A"]]
    assert tables[1].cells == [["B"]]


def test_parse_tables_empty_input() -> None:
    """No TABLE blocks yields no tables."""
    assert TextractParser._parse_tables([], {}) == []


# ---------------------------------------------------------------------------
# _get_cell_text
# ---------------------------------------------------------------------------


def test_get_cell_text_joins_words_with_spaces() -> None:
    """Word children are joined in relationship order with single spaces."""
    cell = _cell_block("c1", 1, 1, ["w1", "w2", "w3"])
    block_map = {
        "w1": _word_block("w1", "Total"),
        "w2": _word_block("w2", "due"),
        "w3": _word_block("w3", "today"),
    }

    assert TextractParser._get_cell_text(cell, block_map) == "Total due today"


def test_get_cell_text_no_relationships() -> None:
    """A cell without relationships has empty text."""
    assert TextractParser._get_cell_text({"BlockType": "CELL", "Id": "c1"}, {}) == ""


def test_get_cell_text_only_non_child_relationships() -> None:
    """Non-CHILD relationships do not contribute words."""
    cell: dict[str, Any] = {
        "BlockType": "CELL",
        "Id": "c1",
        "Relationships": [{"Type": "MERGED_CELL", "Ids": ["m1"]}],
    }

    assert TextractParser._get_cell_text(cell, {"m1": _word_block("m1", "nope")}) == ""


def test_get_cell_text_child_relationship_after_other_types() -> None:
    """The CHILD relationship is used even when listed after another type."""
    cell: dict[str, Any] = {
        "BlockType": "CELL",
        "Id": "c1",
        "Relationships": [
            {"Type": "VALUE", "Ids": ["v1"]},
            {"Type": "CHILD", "Ids": ["w1"]},
        ],
    }

    assert TextractParser._get_cell_text(cell, {"w1": _word_block("w1", "Found")}) == "Found"


def test_get_cell_text_skips_unknown_and_non_word_children() -> None:
    """Missing ids and non-WORD children are skipped."""
    cell = _cell_block("c1", 1, 1, ["missing", "sel1", "w1"])
    block_map = {
        "sel1": {"BlockType": "SELECTION_ELEMENT", "Id": "sel1", "Text": "X"},
        "w1": _word_block("w1", "Kept"),
    }

    assert TextractParser._get_cell_text(cell, block_map) == "Kept"


def test_get_cell_text_word_without_text_key() -> None:
    """A WORD block with no Text contributes an empty token."""
    cell = _cell_block("c1", 1, 1, ["w1", "w2"])
    block_map = {
        "w1": {"BlockType": "WORD", "Id": "w1"},
        "w2": _word_block("w2", "after"),
    }

    assert TextractParser._get_cell_text(cell, block_map) == " after"


# ---------------------------------------------------------------------------
# end-to-end
# ---------------------------------------------------------------------------


def test_parse_response_end_to_end_with_tables(sample_textract_response: dict) -> None:
    """The shared sample response parses into lines, tables and full text."""
    doc = TextractParser.parse_response(sample_textract_response)

    assert len(doc.pages) == 1
    page = doc.pages[0]
    assert [line.text for line in page.lines] == ["Invoice #12345", "Date: 2024-01-15"]
    assert page.tables[0].cells == [["Item", "Price"], ["Product A", "$10"]]
    assert doc.full_text == "Invoice #12345\nDate: 2024-01-15"
    assert doc.metadata["document_metadata"] == {"Pages": 1}


def test_parse_response_multipage_with_table_on_second_page() -> None:
    """Tables are attached to the page their block belongs to."""
    response = {
        "Blocks": [
            {"BlockType": "LINE", "Id": "l1", "Page": 1, "Text": "cover"},
            _table_block("t1", ["c1"], Page=2),
            {"BlockType": "CELL", "Id": "c1", "Page": 2, "RowIndex": 1, "ColumnIndex": 1},
            {"BlockType": "LINE", "Id": "l2", "Page": 2, "Text": "body"},
        ]
    }

    doc = TextractParser.parse_response(response)

    assert len(doc.pages) == EXPECTED_TWO
    assert doc.pages[0].tables == []
    assert len(doc.pages[1].tables) == 1
    assert doc.pages[1].tables[0].cells == [[""]]
    assert doc.full_text == "cover\n\nbody"
