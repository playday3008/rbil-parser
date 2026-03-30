"""File discovery, structured file parsing, metadata and text file parsing."""

from __future__ import annotations

import re
from pathlib import Path

from .blocks import is_divider, is_metadata_divider, parse_divider, parse_entry_line
from .body import parse_body
from .models import (
    DividerInfo,
    Entry,
    EntryType,
    RawBlock,
    Table,
    TextFile,
    TextSection,
)
from .registers import (
    extract_all_table_refs_from_fields,
    parse_register_block,
    parse_return_block,
    parse_see_also,
)

# =============================================================================
# Constants
# =============================================================================

_SUPPLEMENTAL_FILES: dict[str, EntryType] = {
    "PORTS.A": EntryType.PORT,
    "PORTS.B": EntryType.PORT,
    "PORTS.C": EntryType.PORT,
    "MEMORY.LST": EntryType.MEM,
    "CMOS.LST": EntryType.CMOS,
    "FARCALL.LST": EntryType.CALL,
    "MSR.LST": EntryType.MSR,
    "I2C.LST": EntryType.I2C,
    "OPCODES.LST": EntryType.OPCODE,
}


# =============================================================================
# File discovery
# =============================================================================


def find_file(base_dir: Path, name: str) -> Path | None:
    """Find a file by name anywhere under base_dir (recursive)."""
    for p in base_dir.rglob(name):
        if p.is_file():
            return p
    return None


def find_all_data_files(base_dir: Path) -> list[tuple[Path, EntryType | None]]:
    """Find all data files with their entry types. None means text-only file."""
    files: list[tuple[Path, EntryType | None]] = []
    # INTERRUP files
    for f in sorted(base_dir.rglob("INTERRUP.*")):
        suffix = f.suffix.lstrip(".")
        if len(suffix) == 1 and suffix.isalpha() and suffix.upper() <= "R":
            files.append((f, EntryType.INT))
    # Supplemental structured files
    for name, etype in _SUPPLEMENTAL_FILES.items():
        p = find_file(base_dir, name)
        if p:
            files.append((p, etype))
    return files


# =============================================================================
# Metadata / text file parsing
# =============================================================================


def parse_metadata_blocks(
    lines: list[str], all_blocks: bool = False
) -> list[tuple[str, str]]:
    """Extract metadata sections from file headers and tails (! divider blocks).

    Returns list of (name, content) pairs to avoid overwriting duplicates.
    If all_blocks=False, stops at first non-metadata divider.
    If all_blocks=True, scans entire file for all metadata blocks.
    """
    sections: list[tuple[str, str]] = []
    current_name: str | None = None
    current_lines: list[str] = []
    past_first_entry = False

    for line in lines:
        if is_divider(line) and is_metadata_divider(line):
            if current_name and current_lines:
                sections.append((current_name, "\n".join(current_lines).strip()))
            m = re.match(r"^--------!---(\w+)-+", line)
            current_name = m.group(1) if m else "unknown"
            current_lines = []
        elif is_divider(line) and not is_metadata_divider(line):
            if current_name and current_lines:
                sections.append((current_name, "\n".join(current_lines).strip()))
                current_name = None
                current_lines = []
            if not all_blocks and not past_first_entry:
                past_first_entry = True
                if not all_blocks:
                    # Continue scanning to find tail metadata
                    pass
        else:
            if current_name is not None:
                current_lines.append(line.rstrip())

    # Flush last section
    if current_name and current_lines:
        sections.append((current_name, "\n".join(current_lines).strip()))

    return sections


def parse_categories(text: str) -> dict[str, str]:
    """Parse the CATEGORIES block into a dict."""
    cats: dict[str, str] = {}
    for m in re.finditer(r"\b([A-Za-z*])\s*-\s*([^,\n]+)", text):
        cats[m.group(1)] = m.group(2).strip()
    return cats


def parse_file_map(text: str) -> dict[str, str]:
    """Parse the FILELIST block into a file->description map."""
    fmap: dict[str, str] = {}
    for m in re.finditer(r"\t(\S+\.?\S*)\s+(.+)", text):
        fmap[m.group(1)] = m.group(2).strip()
    return fmap


def parse_text_file(filepath: Path) -> TextFile:
    """Parse a plain text file into sections."""
    text = filepath.read_bytes().decode("cp437", errors="replace")
    lines = text.splitlines()
    sections: list[TextSection] = []
    current: list[str] = []
    current_title: str | None = None

    for line in lines:
        stripped = line.rstrip()
        if is_divider(stripped):
            if current:
                sections.append(
                    TextSection(title=current_title, content="\n".join(current).strip())
                )
                current = []
            current_title = stripped
        else:
            current.append(stripped)

    if current:
        sections.append(
            TextSection(title=current_title, content="\n".join(current).strip())
        )
    return TextFile(sections=sections)


# =============================================================================
# Structured file parsing
# =============================================================================


def parse_structured_file(
    filepath: Path, default_type: EntryType, warnings: list[str]
) -> tuple[list[Entry], list[Table], list[tuple[str, str]], list[str]]:
    """Returns (entries, tables, metadata_sections, uncaptured_text_blocks)."""
    entries: list[Entry] = []
    tables: list[Table] = []
    uncaptured: list[str] = []
    filename = filepath.name

    text = filepath.read_bytes().decode("cp437", errors="replace")
    all_lines = text.splitlines()

    # Extract ALL metadata blocks (headers + tails)
    meta_sections = parse_metadata_blocks(all_lines, all_blocks=True)

    # Split into blocks
    blocks: list[RawBlock] = []
    current_divider: str | None = None
    current_body: list[str] = []
    current_line_num = 0

    for line_num, line in enumerate(all_lines, 1):
        if is_divider(line):
            if (
                current_divider is not None
                and not current_body
                and all(c == "-" for c in line.strip())
            ):
                current_divider = (
                    current_divider.rstrip("-").rstrip() + line.strip() + "-" * 10
                )
                continue
            if current_divider is not None:
                blocks.append(
                    RawBlock(current_divider, current_body, filename, current_line_num)
                )
            current_divider = line
            current_body = []
            current_line_num = line_num
        else:
            current_body.append(line)
    if current_divider is not None:
        blocks.append(
            RawBlock(current_divider, current_body, filename, current_line_num)
        )

    for block in blocks:
        if is_metadata_divider(block.divider_line):
            continue

        divider = parse_divider(block.divider_line)
        if divider is None:
            # Edge case 1: wrapped divider (INTERRUP.C line 5070)
            if (
                block.body_lines
                and block.body_lines[0].strip()
                and all(c == "-" for c in block.body_lines[0].strip())
            ):
                combined = (
                    block.divider_line.rstrip("-").rstrip()
                    + block.body_lines[0].strip()
                )
                divider = parse_divider(combined + "-" * 20)
                if divider is not None:
                    block.body_lines = block.body_lines[1:]

            # Edge case 2: all-dash separator (OPCODES.LST, SMM.LST) —
            # try to create a synthetic divider from the entry line
            if divider is None and block.body_lines:
                for bl in block.body_lines:
                    stripped_bl = bl.strip()
                    if not stripped_bl:
                        continue
                    ei = parse_entry_line(stripped_bl)
                    if ei is not None:
                        etype, raw_num, _, _, _ = ei
                        divider = DividerInfo(
                            category=None,
                            int_number=raw_num[:2].upper(),
                            function=raw_num[2:].upper() if len(raw_num) > 2 else None,
                            raw_code=raw_num.upper(),
                        )
                        break
                    break  # only check first non-empty line

            if divider is None:
                # Pure separator line — capture body content if it has substance
                body_text = "\n".join(bl.rstrip() for bl in block.body_lines).strip()
                if body_text and len(body_text) > 5:
                    uncaptured.append(body_text)
                elif not all(c == "-" for c in block.divider_line.strip()):
                    warnings.append(
                        f"{filename}:{block.source_line}: Unparsed divider: {block.divider_line[:50]}"
                    )
                continue

        if not block.body_lines:
            continue

        idx = 0
        while idx < len(block.body_lines) and not block.body_lines[idx].strip():
            idx += 1
        if idx >= len(block.body_lines):
            continue

        entry_info = parse_entry_line(block.body_lines[idx])
        if entry_info is None:
            warnings.append(
                f"{filename}:{block.source_line}: No entry line: {block.body_lines[idx][:60]}"
            )
            continue

        etype, raw_num, flags, title, type_fields = entry_info
        remaining = block.body_lines[idx + 1 :]

        fields, block_tables, input_reg_lines, return_raw_lines = parse_body(remaining)

        entry_id = f"{divider.category or '-'}-{divider.raw_code}"
        input_registers = parse_register_block(input_reg_lines)
        returns = parse_return_block(return_raw_lines)

        sa_raw = fields.get("see_also", "")
        if isinstance(sa_raw, list):
            sa_text = ", ".join(sa_raw)
        else:
            sa_text = sa_raw
        see_also = parse_see_also(sa_text) if sa_text else []

        def _text(key: str) -> str | None:
            v = fields.get(key)
            if v is None:
                return None
            return "\n".join(v) if isinstance(v, list) else v

        def _list(key: str) -> list[str]:
            v = fields.get(key, [])
            return v if isinstance(v, list) else [v]

        table_ids = [t.id for t in block_tables]
        all_refs = extract_all_table_refs_from_fields(fields)

        entry = Entry(
            entry_type=etype,
            id=entry_id,
            category=divider.category,
            title=title,
            source=f"{filename}:{block.source_line}",
            flags=flags,
            function=divider.function,
            input_registers=input_registers,
            returns=returns,
            description=_text("description"),
            program=_text("program"),
            notes=_list("notes"),
            bugs=_list("bugs"),
            see_also=see_also,
            install_check=_text("install_check"),
            range=_text("range"),
            size=_text("size"),
            access=_text("access"),
            index=_list("index"),
            warning=_text("warning"),
            example=_text("example"),
            tables=table_ids,
            table_refs=all_refs,
            **{k: v for k, v in type_fields.items() if v is not None},
        )

        entries.append(entry)
        tables.extend(block_tables)

    return entries, tables, meta_sections, uncaptured
