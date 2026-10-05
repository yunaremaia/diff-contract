# Configuration

The contract lives in `.diffcontract.yml` at the repository root by default.
Pass `--contract PATH` to `check` or `validate` to read it from elsewhere.

## File format

```yaml
version: 1
rules:
  - name: "Block core changes"
    deny:
      - "src/core/**"
      - "*.env"
    on_violation: block

  - name: "Feature development"
    allow:
      - "src/features/**"
    max_files: 15
    max_lines: 400
    on_violation: block
```

## Top-level keys

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `version` | integer | `1` | Contract format version |
| `rules` | list | `[]` | The rules, evaluated in order |

`version` is recorded but not validated — any value parses. A contract with no
`rules` key, or an empty list, accepts every file.

## Rule keys

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `name` | string | `rule-<index>` | Label used in violation messages and JSON |
| `allow` | list of globs | `[]` | Permitted paths; if set, anything unmatched is a violation |
| `deny` | list of globs | `[]` | Forbidden paths; always wins over `allow` |
| `on_violation` | `block` \| `warn` \| `info` | `block` | Severity when this rule is violated |
| `max_files` | integer or unset | unset | Max changed files in the whole diff |
| `max_lines` | integer or unset | unset | Max changed lines in the whole diff |

`name` matters: it is the only thing tying a violation back to a rule in the
output, so give rules names a reviewer can act on.

## Validation errors

The parser fails closed rather than silently accepting a broken contract.

`allow` and `deny` must be **lists of strings**. A bare string is the common
mistake — YAML happily parses `allow: src/**` as a string, and `tuple()` would
split it into one-character patterns:

```
ERROR: Invalid contract .diffcontract.yml: Invalid 'allow' value at rule 1:
expected a list of glob strings, got the string 'src/**'. Did you mean:
  allow:
    - "src/**"
```

Correct form:

```yaml
allow:
  - "src/**"
```

Non-list, non-string values and lists containing non-strings are rejected with
the same style of message. An unknown `on_violation` value lists the valid
ones.

Any parse failure makes the command print `ERROR: Invalid contract ...` and exit
`1` — it never falls back to "allow everything".

## init templates

`diff-contract init` writes a commented starter contract:

```bash
diff-contract init --template docs
```

```
✓ Created .diffcontract.yml (template: docs)
```

| Template | Shape |
|----------|-------|
| `python` (default) | Blocks CI configs and Dockerfile, allows `src/features/**` with a 15-file / 400-line budget, warns above 20 files / 500 lines |
| `react` | Blocks root config (`package.json`, `tsconfig.json`, `.env*`), allows `app/`, `components/`, `lib/`, `pages/`, `src/`, `styles/`, `public/` |
| `django` | Blocks deployment config, `manage.py`, `project/settings/*.py`, `pyproject.toml`, `requirements/*.txt`; allows `apps/`, `templates/`, `static/`, `media/` |
| `rust` | Blocks CI configs, `rust-toolchain.toml`, `Cargo.toml`, `Cargo.lock`, `deny.toml`, `clippy.toml`, `rustfmt.toml`; allows `crates/`, `src/`, `tests/`, `benches/`, `examples/` |
| `docs` | Blocks source code entirely (`src/**`, `*.py`, `*.js`, `*.ts`, `*.rs`, `*.go`); allows `docs/**`, `*.md`, `*.rst` |

Existing files are never overwritten — `init` warns and exits `1`.

The same contracts are in the [`examples/`](https://github.com/yunaremaia/diff-contract/tree/main/examples)
directory, plus a `strict.yml` that denies auth, crypto and infrastructure
paths and gives bugfix work a 5-file / 200-line budget. Copy any of them to your
repository root as `.diffcontract.yml` and edit.

## Next steps

- [Rules](rules.md) — how globs match and rules interact
- [Usage](usage.md) — `--contract` and the other flags
- [CI](ci.md) — point the action at your contract
