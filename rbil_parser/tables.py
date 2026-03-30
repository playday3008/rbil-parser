"""Table row parsing."""

import re

from .models import TableRow, TableType

# =============================================================================
# Regexes
# =============================================================================

# Format table row: " 00h  BYTE  description" or " 00h  4 BYTEs  description"
FORMAT_ROW_RE = re.compile(r"^\s+([0-9A-Fa-f]+h?)\s+(\d*\s*(?:BYTE|WORD|DWORD|BYTEs|WORDs|DWORDs|var)\S*)\s+(.*)")
# Values table row: " 00h  description"
VALUES_ROW_RE = re.compile(r"^\s+([0-9A-Fa-f]+h?(?:\s*[-/]\s*[0-9A-Fa-f]+h?)?)\s+(.*)")
# Bitfields table row: " 0  description" or " 2-3  description"
BITFIELD_ROW_RE = re.compile(r"^\s+((?:bits?\s+)?\d+(?:\s*[-,]\s*\d+)?)\s+(.*)")


# =============================================================================
# Table row parsing
# =============================================================================


def parse_table_rows(table_type: TableType, raw_lines: list[str]) -> list[TableRow]:
    """Parse raw table lines into structured TableRow objects."""
    rows: list[TableRow] = []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip header lines
        if (
            stripped.startswith("Offset")
            or stripped.startswith("Bit(s)")
            or stripped.startswith("Values ")
            or stripped.startswith("Format ")
            or stripped.startswith("Bitfields ")
            or stripped.startswith("Call ")
        ):
            continue
        if table_type == TableType.FORMAT:
            m = FORMAT_ROW_RE.match(line)
            if m:
                rows.append(
                    TableRow(
                        value=m.group(1),
                        size=m.group(2).strip(),
                        description=m.group(3).strip(),
                    )
                )
                continue
        if table_type == TableType.BITFIELDS:
            m = BITFIELD_ROW_RE.match(stripped)
            if m:
                rows.append(
                    TableRow(value=m.group(1).strip(), description=m.group(2).strip())
                )
                continue
        if table_type in (TableType.VALUES, TableType.FORMAT, TableType.BITFIELDS):
            m = VALUES_ROW_RE.match(line)
            if m:
                rows.append(
                    TableRow(value=m.group(1).strip(), description=m.group(2).strip())
                )
                continue
        # Continuation of previous row
        if rows and stripped:
            rows[-1].description += " " + stripped
    return rows
