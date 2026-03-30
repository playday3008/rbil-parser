"""YAML output and main CLI orchestration."""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from .files import (
    find_file,
    find_all_data_files,
    parse_categories,
    parse_file_map,
    parse_structured_file,
    parse_text_file,
)
from .models import (
    Entry,
    EntryFile,
    EntryType,
    ReleaseMetadata,
    Table,
    TableFile,
)


def write_yaml(data: dict[str, Any], filepath: Path) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(
            data,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=120,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse Ralf Brown's Interrupt List (Release 61) into structured YAML.",
    )
    parser.add_argument(
        "input_dir",
        type=Path,
        help="Path to the RBIL data directory (containing inter61a/ through inter61f/)",
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Path to write YAML output files",
    )
    args = parser.parse_args()

    base_dir: Path = args.input_dir.resolve()
    output_dir: Path = args.output_dir.resolve()

    if not base_dir.is_dir():
        print(f"Error: input directory does not exist: {base_dir}", file=sys.stderr)
        sys.exit(1)

    print("Finding all data files...")
    data_files = find_all_data_files(base_dir)
    print(f"  Found {len(data_files)} structured data files")

    all_entries: list[Entry] = []
    all_tables: list[Table] = []
    warnings: list[str] = []
    all_meta_sections: list[tuple[str, str]] = []
    all_uncaptured: dict[str, list[str]] = {}

    for filepath, etype in data_files:
        if etype is None:
            continue
        print(f"  Parsing {filepath.name}...", end="", flush=True)
        entries, tables, meta, uncaptured = parse_structured_file(
            filepath, etype, warnings
        )
        print(
            f" {len(entries)} entries, {len(tables)} tables"
            + (f", {len(uncaptured)} uncaptured blocks" if uncaptured else "")
        )
        all_entries.extend(entries)
        all_tables.extend(tables)
        all_meta_sections.extend(meta)
        if uncaptured:
            all_uncaptured[filepath.name] = uncaptured

    print(
        f"\nTotal: {len(all_entries)} entries, {len(all_tables)} tables, {len(warnings)} warnings"
    )

    # Build metadata lookup (keep all values, don't overwrite duplicates)
    meta_by_name: dict[str, list[str]] = defaultdict(list)
    for name, content in all_meta_sections:
        meta_by_name[name].append(content)

    def _meta(name: str) -> str:
        vals = meta_by_name.get(name, [])
        return "\n\n---\n\n".join(vals) if vals else ""

    # Group entries by type and key
    int_entries: dict[str, list[Entry]] = defaultdict(list)
    port_entries: list[Entry] = []
    other_entries: dict[str, list[Entry]] = defaultdict(list)

    for entry in all_entries:
        if entry.entry_type == EntryType.INT:
            int_num = entry.id[2:4].upper()
            int_entries[int_num].append(entry)
        elif entry.entry_type == EntryType.PORT:
            port_entries.append(entry)
        else:
            other_entries[entry.entry_type.value.lower()].append(entry)

    # Write interrupt files
    int_dir = output_dir / "interrupts"
    int_dir.mkdir(parents=True, exist_ok=True)
    for int_num in sorted(int_entries.keys()):
        ef = EntryFile(file_type="interrupt", key=int_num, entries=int_entries[int_num])
        write_yaml(
            ef.model_dump(mode="json", exclude_none=True),
            int_dir / f"int_{int_num.lower()}.yaml",
        )
    print(f"  Wrote {len(int_entries)} interrupt files")

    # Write port file
    if port_entries:
        ef = EntryFile(file_type="port", key="all", entries=port_entries)
        write_yaml(
            ef.model_dump(mode="json", exclude_none=True), output_dir / "ports.yaml"
        )
        print(f"  Wrote {len(port_entries)} port entries")

    # Write other entry type files
    for type_name, ents in sorted(other_entries.items()):
        ef = EntryFile(file_type=type_name, key="all", entries=ents)
        write_yaml(
            ef.model_dump(mode="json", exclude_none=True),
            output_dir / f"{type_name}.yaml",
        )
        print(f"  Wrote {len(ents)} {type_name} entries")

    # Write tables (deduplicate by ID, keep first occurrence)
    seen_ids: set[str] = set()
    deduped_tables: list[Table] = []
    for t in all_tables:
        if t.id not in seen_ids:
            seen_ids.add(t.id)
            deduped_tables.append(t)
    tf = TableFile(tables=deduped_tables)
    write_yaml(tf.model_dump(mode="json"), output_dir / "tables.yaml")
    print(f"  Wrote {len(deduped_tables)} tables (deduped from {len(all_tables)})")

    # Write text files
    text_file_map: dict[str, str] = {
        "GLOSSARY.LST": "glossary.yaml",
        "BIBLIO.LST": "bibliography.yaml",
        "OVERVIEW.LST": "overview.yaml",
        "86BUGS.LST": "cpu_bugs.yaml",
        "SMM.LST": "smm.yaml",
        "INTERRUP.PRI": "primer.yaml",
        "TABLES.LST": "tables_index.yaml",
        "INTERRUP.1ST": "readme.yaml",
    }
    for src_name, outname in text_file_map.items():
        p = find_file(base_dir, src_name)
        if p:
            tf_data = parse_text_file(p)
            write_yaml(
                tf_data.model_dump(mode="json", exclude_none=True),
                output_dir / outname,
            )
            print(f"  Wrote {outname} ({len(tf_data.sections)} sections)")

    # Write uncaptured content blocks (OPCODES appendices, CMOS separator text, etc.)
    if all_uncaptured:
        uncap_data: dict[str, list[str]] = all_uncaptured
        write_yaml(uncap_data, output_dir / "uncaptured_content.yaml")
        total_blocks = sum(len(v) for v in uncap_data.values())
        print(
            f"  Wrote uncaptured_content.yaml ({total_blocks} blocks from {len(uncap_data)} files)"
        )

    # Extract release info from first line of first parsed file
    first_interrup = find_file(base_dir, "INTERRUP.A")
    release_line = ""
    copyright_line = ""
    if first_interrup:
        first_data = first_interrup.read_bytes().decode("cp437", errors="replace")
        first_lines = first_data.splitlines()
        release_line = first_lines[0] if first_lines else ""
        copyright_line = first_lines[1] if len(first_lines) > 1 else ""

    release_num = 61
    m = re.search(r"Release\s+(\d+)", release_line)
    if m:
        release_num = int(m.group(1))
    last_change = ""
    m = re.search(r"Last change\s+(\S+)", release_line)
    if m:
        last_change = m.group(1)

    # Write metadata with ALL metadata sections from all files
    categories = parse_categories(_meta("CATEGORIES"))
    file_map = parse_file_map(_meta("FILELIST"))

    metadata = ReleaseMetadata(
        release=release_num,
        last_change=last_change,
        copyright=copyright_line.strip(),
        disclaimer=_meta("DISCLAIMER"),
        flags_explanation=_meta("FLAGS"),
        categories=categories,
        file_map=file_map,
        warnings=warnings,
        total_entries=len(all_entries),
        total_tables=len(deduped_tables),
        source_files=[f.name for f, _ in data_files],
    )
    meta_dict = metadata.model_dump(mode="json")
    # Add all raw metadata sections for completeness
    meta_dict["all_metadata_sections"] = [
        {"name": name, "content": content} for name, content in all_meta_sections
    ]
    write_yaml(meta_dict, output_dir / "metadata.yaml")
    print(
        f"  Wrote metadata.yaml ({len(all_meta_sections)} metadata sections from all files)"
    )

    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings[:20]:
            print(f"  {w}")
        if len(warnings) > 20:
            print(f"  ... and {len(warnings) - 20} more (see metadata.yaml)")
