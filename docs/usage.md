# Usage

Three commands: `check`, `validate` and `init`.

```bash
diff-contract check     # diff the current branch against a base branch
diff-contract validate  # validate an explicit file list, no git required
diff-contract init      # write a starter .diffcontract.yml
```

`--version` prints the installed version and exits.

## `check`

```bash
diff-contract check [options]
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--contract PATH` | `.diffcontract.yml` | Contract file to load |
| `--base BRANCH` | `main` | Base branch for `git diff --numstat BASE...HEAD` |
| `--output {text,json}` | `text` | Output format |
| `--sarif` | off | Emit SARIF 2.1.0 instead of the chosen format |
| `--files [PATH...]` | — | Validate these paths instead of diffing |

Without `--files`, the changed-file list comes from git. If the contract is
missing, unreadable, or malformed, the command prints `ERROR: ...` to stderr
and exits `1`. If git itself fails — no such base branch, not a git repository —
the git error is printed and the exit code is `1`.

Passing `--files` with no values is treated as "no file list", so `check` falls
back to the git diff.

### JSON output

```bash
diff-contract check --output json
```

```json
{
  "clean": false,
  "block_count": 1,
  "warn_count": 1,
  "violations": [
    {
      "file": "nope.py",
      "severity": "block",
      "rule": "Only md",
      "message": "File 'nope.py' not allowed by rule 'Only md'"
    },
    {
      "file": "<aggregate>",
      "severity": "warn",
      "rule": "Size guard",
      "message": "Too many lines changed (9 > 2)"
    }
  ]
}
```

`block_count` and `warn_count` count only `block` and `warn` severities. A rule
using `on_violation: info` contributes a violation to the list and sets
`clean: false`, but is counted in neither field.

### SARIF output

```bash
diff-contract check --sarif > diff-contract.sarif
```

See [CI](ci.md#github-code-scanning).

## `validate`

```bash
diff-contract validate [options]
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--contract PATH` | `.diffcontract.yml` | Contract file to load |
| `--files [PATH...]` | — | Paths to validate |
| `--from-stdin` | off | Read one path per line from stdin |
| `--output {text,json}` | `text` | Output format |
| `--sarif` | off | Emit SARIF 2.1.0 instead of the chosen format |

`--from-stdin` takes precedence over `--files` when both are given. Blank lines
are skipped.

```bash
diff-contract validate --files src/app.py tests/test_app.py
git diff --name-only main...HEAD | diff-contract validate --from-stdin
```

`--sarif` and `--output json` behave the same as in `check`.

!!! note "Line counts are zero in `validate`"
    `validate` receives paths, not diffs, so it has no added/deleted line data.
    Every file contributes `0` to `max_lines`, which means **`max_lines` never
    triggers under `validate`**. `max_files` still works, because it counts
    entries in the list. Use `check` when you need line budgets enforced.

## `init`

```bash
diff-contract init [--template {python,react,django,rust,docs}]
```

Writes `.diffcontract.yml` in the current directory. Existing files are never
overwritten — the command warns and exits `1`.

```bash
diff-contract init --template docs
```

```
✓ Created .diffcontract.yml (template: docs)
```

## Exit codes

The same contract for every command:

| Code | Meaning |
|------|---------|
| `0` | Clean, or only `info` violations |
| `1` | At least one `block` violation, or an error (missing contract, bad YAML, git failure, no file list) |
| `2` | No block violations, but at least one `warn` violation |

This holds for `init` too, where `1` means "a contract already exists". The
`--version` flag exits `0`.

Because warnings and errors share `1` with blocks, a CI script that needs to
tell them apart should read `--output json` and check `block_count` rather than
relying on the exit code alone.

## Next steps

- [Rules](rules.md) — what the globs actually match
- [Configuration](configuration.md) — the contract file format
- [API Reference](api.md) — calling the engine from Python
