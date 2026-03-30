"""Pydantic models and data types for RBIL parser."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class EntryFlag(str, Enum):
    UNDOCUMENTED = "U"
    PARTIALLY_DOCUMENTED = "u"
    PROTECTED_MODE = "P"
    REAL_MODE = "R"
    CALLBACK = "C"
    OBSOLETE = "O"


class EntryType(str, Enum):
    INT = "INT"
    PORT = "PORT"
    MEM = "MEM"
    CMOS = "CMOS"
    CALL = "CALL"
    MSR = "MSR"
    I2C = "I2C"
    OPCODE = "OPCODE"


class TableType(str, Enum):
    FORMAT = "format"
    VALUES = "values"
    BITFIELDS = "bitfields"
    CALL = "call"


# =============================================================================
# Structured register / return / sub-value models
# =============================================================================


class SubValue(BaseModel):
    value: str
    description: str
    sub_values: list[SubValue] = Field(default_factory=list["SubValue"])


class RegisterValue(BaseModel):
    reg: str
    operator: str
    value: str | None = None
    description: str | None = None
    table_refs: list[str] = Field(default_factory=list)
    sub_values: list[SubValue] = Field(default_factory=list[SubValue])


class ReturnBranch(BaseModel):
    condition: str | None = None
    condition_description: str | None = None
    registers: list[RegisterValue] = Field(default_factory=list[RegisterValue])
    raw_lines: list[str] = Field(default_factory=list)


# =============================================================================
# Typed cross-references
# =============================================================================


class InterruptRef(BaseModel):
    type: Literal["interrupt"] = "interrupt"
    interrupt: str | None = None
    params: dict[str, str] = Field(default_factory=dict)
    name: str | None = None


class TableRef(BaseModel):
    type: Literal["table"] = "table"
    id: str


class PortRef(BaseModel):
    type: Literal["port"] = "port"
    port: str
    name: str | None = None


class MemoryRef(BaseModel):
    type: Literal["memory"] = "memory"
    address: str


class OpcodeRef(BaseModel):
    type: Literal["opcode"] = "opcode"
    mnemonic: str


CrossReference = Annotated[
    Union[InterruptRef, TableRef, PortRef, MemoryRef, OpcodeRef],
    Field(discriminator="type"),
]


# =============================================================================
# Structured table rows
# =============================================================================


class TableRow(BaseModel):
    value: str
    size: str | None = None
    description: str
    sub_rows: list[TableRow] = Field(default_factory=list["TableRow"])


class Table(BaseModel):
    id: str  # "00729" or "S0001" for SMM tables
    type: TableType
    title: str
    column_headers: list[str] | None = None
    rows: list[TableRow] = Field(default_factory=list[TableRow])
    raw_lines: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    see_also: list[CrossReference] = Field(default_factory=list[CrossReference])


# =============================================================================
# Entry model (all types)
# =============================================================================


class Entry(BaseModel):
    entry_type: EntryType
    id: str
    category: str | None = None
    title: str
    source: str
    # Type-specific title fields
    interrupt: str | None = None
    port_range: str | None = None
    address: str | None = None
    cmos_byte: str | None = None
    call_address: str | None = None
    msr_address: str | None = None
    i2c_address: str | None = None
    opcode_mnemonic: str | None = None
    # Common fields
    flags: list[EntryFlag] = Field(default_factory=list[EntryFlag])
    function: str | None = None
    input_registers: list[RegisterValue] = Field(default_factory=list[RegisterValue])
    returns: list[ReturnBranch] = Field(default_factory=list[ReturnBranch])
    description: str | None = None
    program: str | None = None
    notes: list[str] = Field(default_factory=list)
    bugs: list[str] = Field(default_factory=list)
    see_also: list[CrossReference] = Field(default_factory=list[CrossReference])
    install_check: str | None = None
    range: str | None = None
    size: str | None = None
    access: str | None = None
    index: list[str] = Field(default_factory=list)
    warning: str | None = None
    example: str | None = None
    tables: list[str] = Field(default_factory=list)
    table_refs: list[str] = Field(default_factory=list)


# =============================================================================
# File-level models
# =============================================================================


class EntryFile(BaseModel):
    file_type: str
    key: str
    entries: list[Entry]


class TableFile(BaseModel):
    tables: list[Table]


class ReleaseMetadata(BaseModel):
    release: int
    last_change: str
    copyright: str
    disclaimer: str
    flags_explanation: str
    categories: dict[str, str]
    file_map: dict[str, str]
    warnings: list[str]
    total_entries: int
    total_tables: int
    source_files: list[str]


class TextSection(BaseModel):
    title: str | None = None
    content: str


class TextFile(BaseModel):
    sections: list[TextSection]


# =============================================================================
# Dataclasses (non-Pydantic data carriers)
# =============================================================================


@dataclass
class DividerInfo:
    category: str | None
    int_number: str
    function: str | None
    raw_code: str


@dataclass
class RawBlock:
    divider_line: str
    body_lines: list[str]
    source_file: str
    source_line: int


# =============================================================================
# Type aliases
# =============================================================================

ParserReturnType = (
    tuple[EntryType, str, list[EntryFlag], str, dict[str, str | None]] | None
)
