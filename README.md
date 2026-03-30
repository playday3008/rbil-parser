# rbil-parser

Parser for [Ralf Brown's Interrupt List](https://www.cs.cmu.edu/~ralf/files.html) (Release 61) into structured YAML.

Pre-generated output is available at [**rbil-yaml**](https://github.com/playday3008/rbil-yaml).

## Usage

```sh
uv run parse-rbil <input_dir> <output_dir>
```

- `input_dir` — path to the RBIL data directory (containing `inter61a/` through `inter61f/`)
- `output_dir` — path to write YAML output files

## Output

- `interrupts/int_XX.yaml` — one file per interrupt number
- `ports.yaml` — I/O port entries
- `tables.yaml` — reference tables
- `metadata.yaml` — release info, categories, and file map
- Additional files for glossary, bibliography, CPU bugs, SMM, etc.

## Known Parsing Limitations

The following are not fully parsed and end up as raw text, fallback types, or dropped entirely:

- **Return registers** — lines in `Return:` blocks that don't match register syntax or CF/`---if` conditions are stored as `raw_lines` strings rather than structured register objects.
- **Cross-references** — MSR, CMOS, and I2C references in `SeeAlso` lack dedicated reference types and fall back to a generic `InterruptRef` with just a `name` field.
- **Table rows** — rows that don't match the value/bitfield/format regex are silently appended to the previous row's description, which can mangle data if a row has unusual formatting.
- **Sub-values** — in register sub-value lists, lines not matching the hex or bit-range patterns are silently dropped if there's no prior result to append to.
- **Unparseable dividers** — blocks whose divider line can't be parsed (malformed or wrapped) are either captured as uncaptured content or skipped entirely.
- **Blocks without entry lines** — if the first non-empty line after a divider doesn't match any known entry prefix (`INT`, `PORT`, `MEM`, etc.), the entire block is skipped.
- **Unrecognized field labels** — only the labels in the hardcoded `FIELD_LABELS` set are detected; any other label-like lines are not identified as fields.
- **Entry flags** — invalid flag characters in divider lines are silently discarded.

## License

MIT
