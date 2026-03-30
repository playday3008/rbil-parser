"""Register, return, and see-also parsers with cross-reference extraction."""

from __future__ import annotations

import re

from .models import (
    CrossReference,
    InterruptRef,
    MemoryRef,
    OpcodeRef,
    PortRef,
    RegisterValue,
    ReturnBranch,
    SubValue,
    TableRef,
)

# =============================================================================
# Regexes
# =============================================================================

# fmt: off

REGISTERS: set[str] = {
    "AL", "AH", "BL", "BH", "CL", "CH", "DL", "DH",
    "AX", "BX", "CX", "DX", "SI", "DI", "SP", "BP",
    "CS", "DS", "ES", "SS", "FS", "GS",
    "EAX", "EBX", "ECX", "EDX", "ESI", "EDI", "ESP", "EBP",
    "CF", "ZF", "SF", "IF",
}

# fmt: on

REGISTER_LINE_RE = re.compile(r"^([A-Z]{2,3}(?::[A-Z]{2,3})?)\s+(=|->|clear|set)\s*(.*)")
HEX_VALUE_RE = re.compile(r"^([0-9A-Fa-f]+h)\b\s*(.*)")
SUB_VALUE_HEX_RE = re.compile(r"^([0-9A-Fa-f]+h?)\s+(.*)")
SUB_VALUE_BIT_RE = re.compile(r"^(bits?\s+\d+(?:[,\-]\d+)*)\s+(.*)")
TABLE_REF_ALL_RE = re.compile(r"#(\d{4,5})")

SEEALSO_INT_RE = re.compile(r'^INT\s+([0-9A-Fa-f]+)(?:/([^",]+))?\s*(?:"([^"]*)")?$')
SEEALSO_PARAM_RE = re.compile(r"([A-Z]{2})=([0-9A-Fa-f]+h?)")
SEEALSO_TABLE_RE = re.compile(r"^#(\d+)$")
SEEALSO_PORT_RE = re.compile(r'^PORT\s+([0-9A-Fa-f]+h?)(?:"([^"]*)")?$')
SEEALSO_MEM_RE = re.compile(r"^MEM\s+([0-9A-Fa-f]+h?:[0-9A-Fa-f]+h?)$")
SEEALSO_OPCODE_RE = re.compile(r'^OPCODE\s+"([^"]*)"$')
SEEALSO_REG_RE = re.compile(r'^([A-Z]{2})=([0-9A-Fa-f]+h?)(?:"([^"]*)")?$')


# =============================================================================
# Table-ref extraction
# =============================================================================


def extract_table_refs(text: str) -> list[str]:
    return [m.group(1) for m in TABLE_REF_ALL_RE.finditer(text)]


def extract_all_table_refs_from_fields(
    fields: dict[str, str | list[str]],
) -> list[str]:
    """Extract table refs from ALL text fields."""
    refs: set[str] = set()
    # fmt: off
    for _, val in fields.items():
        if isinstance(val, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            refs.update(extract_table_refs(val))
        elif isinstance(val, list):  # pyright: ignore[reportUnnecessaryIsInstance]
            for item in val:
                if isinstance(item, str):  # pyright: ignore[reportUnnecessaryIsInstance]
                    refs.update(extract_table_refs(item))
                else:
                    raise ValueError(f"Unexpected list item type: {type(item)}")
        else:
            raise ValueError(f"Unexpected field value type: {type(val)}")
    # fmt: on
    return sorted(refs)


# =============================================================================
# Register / Return parsers
# =============================================================================


def _indent_level(line: str) -> int:
    count = 0
    for ch in line:
        if ch == "\t":
            count += 4
        elif ch == " ":
            count += 1
        else:
            break
    return count


def _parse_sub_values(lines: list[str], base_indent: int) -> list[SubValue]:
    result: list[SubValue] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        indent = _indent_level(line)
        if indent <= base_indent:
            break
        m = SUB_VALUE_HEX_RE.match(stripped)
        if not m:
            m = SUB_VALUE_BIT_RE.match(stripped)
        if m:
            val, desc = m.group(1), m.group(2).strip()
            sub_lines: list[str] = []
            j = i + 1
            while j < len(lines):
                if not lines[j].strip():
                    j += 1
                    continue
                if _indent_level(lines[j]) > indent:
                    sub_lines.append(lines[j])
                    j += 1
                else:
                    break
            sub_sub = _parse_sub_values(sub_lines, indent) if sub_lines else []
            result.append(SubValue(value=val, description=desc, sub_values=sub_sub))
            i = j
        else:
            if result:
                result[-1].description += " " + stripped
            i += 1
    return result


def _is_register_start(stripped: str) -> bool:
    m = REGISTER_LINE_RE.match(stripped)
    if not m:
        return False
    reg = m.group(1)
    if ":" in reg:
        parts = reg.split(":")
        return parts[0] in REGISTERS and parts[1] in REGISTERS
    return reg in REGISTERS


def _parse_single_register(
    stripped: str, sub_value_lines: list[str], this_indent: int
) -> RegisterValue | None:
    m = REGISTER_LINE_RE.match(stripped)
    if not m:
        return None
    reg, operator, rest = m.group(1), m.group(2), m.group(3).strip()
    if ":" in reg:
        parts = reg.split(":")
        if parts[0] not in REGISTERS or parts[1] not in REGISTERS:
            return None
    elif reg not in REGISTERS:
        return None

    value: str | None = None
    description: str | None = rest if rest else None
    if operator in ("=", "->"):
        hm = HEX_VALUE_RE.match(rest)
        if hm:
            value = hm.group(1)
            leftover = hm.group(2).strip()
            description = leftover if leftover else None
        elif not rest:
            description = None

    table_refs = extract_table_refs(rest) if rest else []
    sub_values = (
        _parse_sub_values(sub_value_lines, this_indent) if sub_value_lines else []
    )

    return RegisterValue(
        reg=reg,
        operator=operator,
        value=value,
        description=description,
        table_refs=table_refs,
        sub_values=sub_values,
    )


def parse_register_block(lines: list[str]) -> list[RegisterValue]:
    result: list[RegisterValue] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        this_indent = _indent_level(line)
        if _is_register_start(stripped):
            sub_lines: list[str] = []
            j = i + 1
            while j < len(lines):
                nl = lines[j]
                ns = nl.strip()
                if not ns:
                    k = j + 1
                    while k < len(lines) and not lines[k].strip():
                        k += 1
                    if (
                        k < len(lines)
                        and _indent_level(lines[k]) > this_indent
                        and not _is_register_start(lines[k].strip())
                    ):
                        sub_lines.append(nl)
                        j += 1
                        continue
                    else:
                        break
                elif _indent_level(nl) > this_indent and not _is_register_start(ns):
                    sub_lines.append(nl)
                    j += 1
                else:
                    break
            rv = _parse_single_register(stripped, sub_lines, this_indent)
            if rv:
                result.append(rv)
            i = j
        else:
            i += 1
    return result


def parse_return_block(lines: list[str]) -> list[ReturnBranch]:
    if not lines:
        return []
    branches: list[ReturnBranch] = []
    current_condition: str | None = None
    current_cond_desc: str | None = None
    current_lines: list[str] = []
    current_raw: list[str] = []

    def flush() -> None:
        nonlocal current_condition, current_cond_desc, current_lines, current_raw
        if current_lines or current_raw or current_condition is not None:
            regs = parse_register_block(current_lines) if current_lines else []
            branches.append(
                ReturnBranch(
                    condition=current_condition,
                    condition_description=current_cond_desc,
                    registers=regs,
                    raw_lines=current_raw,
                )
            )
        current_condition = None
        current_cond_desc = None
        current_lines = []
        current_raw = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        cf_match = re.match(r"^(CF)\s+(clear|set)\s*(.*)", stripped)
        if cf_match:
            flush()
            current_condition = f"CF {cf_match.group(2)}"
            current_cond_desc = cf_match.group(3).strip() or None
            continue
        if_match = re.match(r"^---if\s+(.*)", stripped)
        if if_match:
            flush()
            current_condition = if_match.group(1).strip()
            continue
        if _is_register_start(stripped):
            current_lines.append(line)
        else:
            if current_lines:
                current_lines.append(line)
            else:
                current_raw.append(stripped)
    flush()
    return branches


# =============================================================================
# SeeAlso parser
# =============================================================================


def parse_see_also(text: str) -> list[CrossReference]:
    refs: list[CrossReference] = []
    parts: list[str] = []
    current: list[str] = []
    depth, in_quote = 0, False
    for ch in text:
        if ch == '"':
            in_quote = not in_quote
            current.append(ch)
        elif ch == "(" and not in_quote:
            depth += 1
            current.append(ch)
        elif ch == ")" and not in_quote:
            depth -= 1
            current.append(ch)
        elif ch == "," and not in_quote and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current).strip())

    for part in parts:
        part = part.strip()
        if not part:
            continue
        ref = _parse_single_ref(part)
        if ref:
            refs.append(ref)
    return refs


def _parse_single_ref(text: str) -> CrossReference | None:
    text = text.strip()
    if not text:
        return None
    m = SEEALSO_TABLE_RE.match(text)
    if m:
        return TableRef(id=m.group(1))
    m = SEEALSO_PORT_RE.match(text)
    if m:
        return PortRef(port=m.group(1), name=m.group(2))
    m = SEEALSO_MEM_RE.match(text)
    if m:
        return MemoryRef(address=m.group(1))
    m = SEEALSO_OPCODE_RE.match(text)
    if m:
        return OpcodeRef(mnemonic=m.group(1))
    m = SEEALSO_INT_RE.match(text)
    if m:
        params: dict[str, str] = {}
        if m.group(2):
            for pm in SEEALSO_PARAM_RE.finditer(m.group(2)):
                params[pm.group(1)] = pm.group(2)
        return InterruptRef(
            interrupt=m.group(1).upper(), params=params, name=m.group(3)
        )
    m = SEEALSO_REG_RE.match(text)
    if m:
        return InterruptRef(
            interrupt=None, params={m.group(1): m.group(2)}, name=m.group(3)
        )
    # MSR/CMOS/I2C refs — store full text as name since they don't have a dedicated ref type
    for prefix in ("MSR ", "CMOS ", "I2C "):
        if text.startswith(prefix):
            return InterruptRef(interrupt=None, params={}, name=text)
    # Fallback
    name_m = re.search(r'"([^"]*)"', text)
    name = name_m.group(1) if name_m else None
    params = {}
    for pm in SEEALSO_PARAM_RE.finditer(text):
        params[pm.group(1)] = pm.group(2)
    if params or name:
        return InterruptRef(interrupt=None, params=params, name=name)
    return InterruptRef(interrupt=None, params={}, name=text)
