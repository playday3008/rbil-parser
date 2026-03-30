"""Body parsing — dispatches fields, tables, and register collection."""

from __future__ import annotations

import re

from .blocks import TABLE_ID_RE, detect_field_label, detect_table_start, is_divider
from .models import CrossReference, Table, TableType
from .registers import parse_see_also
from .tables import parse_table_rows


def parse_body(
    lines: list[str],
) -> tuple[dict[str, str | list[str]], list[Table], list[str], list[str]]:
    fields: dict[str, str | list[str]] = {}
    tables: list[Table] = []
    current_field: str | None = None
    current_value_lines: list[str] = []
    collecting_input_regs = True
    input_reg_lines: list[str] = []
    return_raw_lines: list[str] = []
    in_table = False
    table_type = TableType.VALUES
    table_title = ""
    table_id: str | None = None
    table_lines: list[str] = []

    def flush_field() -> None:
        nonlocal current_field, current_value_lines
        if current_field and current_value_lines:
            text = "\n".join(current_value_lines)
            if current_field in fields:
                existing = fields[current_field]
                if isinstance(existing, list):
                    existing.append(text)
                else:
                    fields[current_field] = [existing, text]
            else:
                if current_field in ("notes", "bugs", "index"):
                    fields[current_field] = [text]
                else:
                    fields[current_field] = text
        current_field = None
        current_value_lines = []

    def flush_table() -> None:
        nonlocal in_table, table_lines, table_id, table_title, table_type
        if in_table and (table_lines or table_id is not None):
            tid = table_id
            if tid is None:
                for tl in table_lines:
                    m = TABLE_ID_RE.search(tl)
                    if m:
                        tid = m.group(1)
                        break
            if tid is not None:
                clean = [
                    tl
                    for tl in table_lines
                    if not re.match(r"^\(Table [A-Z]?\d+\)\s*$", tl.strip())
                ]
                rows = parse_table_rows(table_type, clean)
                # Extract Note/Notes and SeeAlso from table raw lines
                table_notes: list[str] = []
                table_see_also: list[CrossReference] = []
                remaining_clean: list[str] = []
                for tl in clean:
                    ts = tl.strip()
                    if ts.startswith("Note:") or ts.startswith("Notes:"):
                        table_notes.append(ts.split(":", 1)[1].strip())
                    elif ts.startswith("SeeAlso:") or ts.startswith("SeeALso:"):
                        table_see_also.extend(
                            parse_see_also(ts.split(":", 1)[1].strip())
                        )
                    else:
                        remaining_clean.append(tl)
                tables.append(
                    Table(
                        id=tid,
                        type=table_type,
                        title=table_title,
                        rows=rows,
                        raw_lines=remaining_clean,
                        notes=table_notes,
                        see_also=table_see_also,
                    )
                )
        in_table = False
        table_lines = []
        table_id = None
        table_title = ""

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip()
        if not stripped:
            if in_table:
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines):
                    nl = lines[j].strip()
                    if (
                        detect_table_start(nl) is not None
                        or detect_field_label(nl) is not None
                        or is_divider(nl)
                    ):
                        flush_table()
                    else:
                        table_lines.append("")
                else:
                    flush_table()
            i += 1
            continue

        table_info = detect_table_start(stripped)
        if table_info is not None:
            if collecting_input_regs:
                collecting_input_regs = False
            flush_field()
            flush_table()
            in_table = True
            table_type, table_title, table_id = table_info
            if re.match(r"^\(Table \d+\)\s*$", stripped):
                table_lines.append(stripped)
                i += 1
                if i < len(lines) and lines[i].strip():
                    ns = lines[i].strip()
                    si = detect_table_start(ns)
                    if si is not None:
                        table_type = si[0]
                        table_title = si[1]
                        if si[2] is not None and table_id is None:
                            table_id = si[2]
                    table_lines.append(lines[i].rstrip())
                    i += 1
                continue
            else:
                table_lines.append(stripped)
                i += 1
                continue

        if in_table:
            table_lines.append(stripped)
            i += 1
            continue

        fi = detect_field_label(stripped)
        if fi is not None:
            if collecting_input_regs:
                collecting_input_regs = False
            flush_field()
            field_name, initial = fi
            if field_name == "return_info":
                if initial:
                    return_raw_lines.append(initial)
                current_field = "__return__"
            else:
                current_field = field_name
                if initial:
                    current_value_lines = [initial]
            i += 1
            continue

        if stripped.startswith("\t") or stripped.startswith("  "):
            if collecting_input_regs and current_field is None:
                input_reg_lines.append(line)
            elif current_field == "__return__":
                return_raw_lines.append(stripped.strip())
            elif current_field is not None:
                current_value_lines.append(stripped.strip())
            i += 1
            continue

        if current_field == "__return__":
            return_raw_lines.append(stripped)
        elif current_field is not None:
            current_value_lines.append(stripped)
        elif collecting_input_regs:
            input_reg_lines.append(line)
        i += 1

    flush_field()
    flush_table()
    return fields, tables, input_reg_lines, return_raw_lines
