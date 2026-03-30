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

## License

MIT
