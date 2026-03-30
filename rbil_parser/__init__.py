"""Zero-loss parser for Ralf Brown's Interrupt List (Release 61) to structured YAML.

Parses ALL data files: INTERRUP.A-R, PORTS.A-C, MEMORY.LST, CMOS.LST, FARCALL.LST,
MSR.LST, I2C.LST, OPCODES.LST, SMM.LST, plus text files (GLOSSARY, BIBLIO, etc.)
and metadata blocks (copyright, disclaimer, categories, etc.).

Uses the same block-detection approach as the bundled INTPRINT.C and INT2GUID.C.
"""

from .files import find_all_data_files, parse_structured_file, parse_text_file
from .models import (
    CrossReference,
    DividerInfo,
    Entry,
    EntryFile,
    EntryFlag,
    EntryType,
    InterruptRef,
    MemoryRef,
    OpcodeRef,
    PortRef,
    RawBlock,
    RegisterValue,
    ReleaseMetadata,
    ReturnBranch,
    SubValue,
    Table,
    TableFile,
    TableRef,
    TableRow,
    TableType,
    TextFile,
    TextSection,
)
from .output import main, write_yaml

__all__ = [
    "CrossReference",
    "DividerInfo",
    "Entry",
    "EntryFile",
    "EntryFlag",
    "EntryType",
    "InterruptRef",
    "MemoryRef",
    "OpcodeRef",
    "PortRef",
    "RawBlock",
    "RegisterValue",
    "ReleaseMetadata",
    "ReturnBranch",
    "SubValue",
    "Table",
    "TableFile",
    "TableRef",
    "TableRow",
    "TableType",
    "TextFile",
    "TextSection",
    "find_all_data_files",
    "main",
    "parse_structured_file",
    "parse_text_file",
    "write_yaml",
]
