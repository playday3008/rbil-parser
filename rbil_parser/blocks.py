"""Divider detection, entry-line parsing, and field-label detection."""

from __future__ import annotations

import re

from .models import DividerInfo, EntryFlag, EntryType, ParserReturnType, TableType

# =============================================================================
# Constants
# =============================================================================

# fmt: off

FLAG_CHARS: set[str] = {"U", "u", "P", "R", "C", "O"}

FIELD_LABELS: dict[str, str] = {
    "Return": "return_info", "Returns": "return_info",
    "Desc": "description",
    "Note": "notes", "Notes": "notes",
    "SeeAlso": "see_also", "SeeALso": "see_also", "See also": "see_also",
    "Program": "program",
    "BUG": "bugs", "BUGS": "bugs", "BUGs": "bugs",
    "Index": "index",
    "Range": "range",
    "InstallCheck": "install_check",
    "Warning": "warning",
    "STACK": "stack", "Legend": "legend",
    "Example": "example",
    "Size": "size", "Access": "access",
}

ENTRY_PREFIXES: dict[str, EntryType] = {
    "INT ": EntryType.INT,
    "PORT ": EntryType.PORT,
    "CMOS ": EntryType.CMOS,
    "MEM ": EntryType.MEM,
    "I2C ": EntryType.I2C,
    "CALL ": EntryType.CALL,
    "OPCODE ": EntryType.OPCODE,
    "MSR ": EntryType.MSR,
}

# fmt: on

TABLE_ID_RE = re.compile(r"\(Table ([A-Z]?\d+)\)")


# =============================================================================
# Divider detection
# =============================================================================


def is_divider(line: str) -> bool:
    return line.startswith("--------")


def is_metadata_divider(line: str) -> bool:
    return len(line) > 8 and line[8] == "!"


def parse_divider(line: str) -> DividerInfo | None:
    stripped = line.rstrip()
    if len(stripped) < 12:
        return None
    # Skip pure separator lines (all dashes, no code) — file terminators
    if all(c == "-" for c in stripped):
        return None
    cat_char = stripped[8]
    if cat_char == "!":
        return None
    if cat_char == "-" and stripped[9] == "-":
        # Could be "----------XXYYZZ---" (no category) or all dashes (separator)
        raw_code = stripped[10:].rstrip("-").rstrip().replace("-", "")
        if not raw_code or len(raw_code) < 2:
            return None
    elif stripped[9] == "-":
        raw_code = stripped[10:].rstrip("-").rstrip().replace("-", "")
        if len(raw_code) < 2:
            return None
    else:
        return None
    int_number = raw_code[:2].upper()
    function = raw_code[2:].upper() if len(raw_code) > 2 else None
    category = cat_char if cat_char != "-" else None
    return DividerInfo(
        category=category,
        int_number=int_number,
        function=function,
        raw_code=raw_code.upper(),
    )


# =============================================================================
# Entry-line parsing
# =============================================================================


def parse_entry_line(line: str) -> ParserReturnType:
    """Parse the entry title line. Returns (type, raw_number, flags, title, type_fields)."""
    stripped = line.strip()
    for prefix, etype in ENTRY_PREFIXES.items():
        if stripped.startswith(prefix):
            rest = stripped[len(prefix) :]
            if etype == EntryType.INT:
                return _parse_int_line(rest, etype)
            elif etype == EntryType.PORT:
                return _parse_port_line(rest, etype)
            elif etype == EntryType.MEM:
                return _parse_generic_addr_line(rest, etype, "address")
            elif etype == EntryType.CMOS:
                return _parse_generic_addr_line(rest, etype, "cmos_byte")
            elif etype == EntryType.CALL:
                return _parse_generic_addr_line(rest, etype, "call_address")
            elif etype == EntryType.MSR:
                return _parse_generic_addr_line(rest, etype, "msr_address")
            elif etype == EntryType.I2C:
                return _parse_generic_addr_line(rest, etype, "i2c_address")
            elif etype == EntryType.OPCODE:
                return _parse_opcode_line(rest, etype)
    return None


def _parse_int_line(rest: str, etype: EntryType) -> ParserReturnType:
    parts = rest.split(None, 1)
    if not parts:
        return None
    num_raw = parts[0]
    if num_raw.lower().endswith("h"):
        num_raw = num_raw[:-1]
    num = num_raw.upper()
    remainder = parts[1] if len(parts) > 1 else ""
    flags: list[EntryFlag] = []
    while remainder and remainder[0] in FLAG_CHARS:
        try:
            flags.append(EntryFlag(remainder[0]))
        except ValueError:
            pass
        remainder = remainder[1:].lstrip()
    if remainder.startswith("-"):
        remainder = remainder[1:].lstrip()
    return etype, num, flags, remainder, {"interrupt": num}


def _parse_port_line(rest: str, etype: EntryType) -> ParserReturnType:
    # "0000-001F - DMA 1 - ..."
    m = re.match(r"^([0-9A-Fa-f]+(?:\s*-\s*[0-9A-Fa-f]+)?h?)\s*-\s*(.*)", rest)
    if m:
        port_range = m.group(1).strip()
        title = m.group(2).strip()
        return etype, port_range, [], title, {"port_range": port_range}
    # Fallback
    parts = rest.split(" - ", 1)
    return (
        etype,
        parts[0].strip(),
        [],
        parts[1].strip() if len(parts) > 1 else rest,
        {"port_range": parts[0].strip()},
    )


def _parse_generic_addr_line(
    rest: str, etype: EntryType, field_name: str
) -> ParserReturnType:
    # "0040h:0017h - description" or "00000000h - description"
    parts = rest.split(" - ", 1)
    addr = parts[0].strip()
    if addr.lower().endswith("h"):
        pass  # fine
    title = parts[1].strip() if len(parts) > 1 else ""
    return etype, addr, [], title, {field_name: addr}


def _parse_opcode_line(rest: str, etype: EntryType) -> ParserReturnType:
    # "AAA   -  ASCII adjust AX after addition"
    parts = rest.split(None, 1)
    if not parts:
        return None
    mnemonic = parts[0].strip()
    remainder = parts[1].strip() if len(parts) > 1 else ""
    if remainder.startswith("-"):
        remainder = remainder[1:].strip()
    return etype, mnemonic, [], remainder, {"opcode_mnemonic": mnemonic}


# =============================================================================
# Table-start and field-label detection
# =============================================================================


def detect_table_start(line: str) -> tuple[TableType, str, str | None] | None:
    stripped = line.strip()
    sm = re.match(r"^\(Table ([A-Z]?\d+)\)\s*$", stripped)
    if sm:
        return TableType.VALUES, "", sm.group(1)
    type_map = {
        "Bitfields ": TableType.BITFIELDS,
        "Call ": TableType.CALL,
        "Format ": TableType.FORMAT,
        "Values ": TableType.VALUES,
    }
    for prefix, tt in type_map.items():
        if stripped.startswith(prefix):
            title_part = stripped[len(prefix) :].rstrip(":")
            table_id: str | None = None
            id_match = TABLE_ID_RE.search(title_part)
            if id_match:
                table_id = id_match.group(1)
                title_part = title_part[: id_match.start()].rstrip()
            return tt, title_part.strip(), table_id
    return None


def detect_field_label(line: str) -> tuple[str, str] | None:
    for label, field_name in FIELD_LABELS.items():
        if line.startswith(label + ":") or line.startswith(label + ":\t"):
            value = line[len(label) + 1 :].strip()
            return field_name, value
    return None
