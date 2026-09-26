# diff-contract

**Deterministic guardrails for AI-generated diffs — define what files can change, block violations.**

```bash
pip install diff-contract
diff-contract check --contract .diffcontract.yml
```

## The Problem

AI coding tools (Cursor, Claude Code, Codex) sometimes modify unrelated files, introduce changes outside the intended scope, or drift from the original structure. `diff-contract` sits between AI-generated code and your repo, enforcing **deterministic** constraints — not relying on another AI pass to review.

> "Most tools either help generate code or review it after the fact, but there's no real control layer in between." — HN discussion, 2026

## Quick Start

### 1. Install
```bash
pip install diff-contract
```

### 2. Define your contract
```yaml
# .diffcontract.yml
version: 1
rules:
  - name: "Block core changes"
    deny:
      - "src/core/**"
      - "*.env"
    on_violation: block

  - name: "Allow feature X"
    allow:
      - "src/features/X/**"
      - "tests/features/X/**"
    on_violation: block
```

### 3. Check your diff
```bash
# Check current branch vs main
diff-contract check

# Check specific files
diff-contract check --files src/app.py src/utils.py

# JSON output (for CI)
diff-contract check --output json
```

### 4. GitHub Action
```yaml
# .github/workflows/diff-contract.yml
name: diff-contract
on: pull_request

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: yunaremaia/diff-contract@main
```

## Validate files (no git required)

Validate specific files against your contract without a git diff — ideal for pre-commit hooks:

```bash
diff-contract validate --files src/app.py tests/test_app.py
echo "src/foo.py" | diff-contract validate --from-stdin
```

## Initialize a contract

Create a starter `.diffcontract.yml`:

```bash
diff-contract init                    # default Python project contract
diff-contract init --template react   # React/Next.js
diff-contract init --template django  # Django
diff-contract init --template rust    # Rust workspace
diff-contract init --template docs    # documentation-only
```

Ready-to-use templates for React, Django, Rust, and documentation-only projects are available in the [`examples/`](examples/) directory.

## Pre-commit hook

diff-contract ships a pre-commit hook. Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/yunaremaia/diff-contract
    rev: v0.1.0
    hooks:
      - id: diff-contract
        args: ["--contract", ".diffcontract.yml"]
```

## SARIF Output (GitHub Code Scanning)

Generate SARIF 2.1.0 output for GitHub Code Scanning integration:

```bash
diff-contract check --sarif > diff-contract.sarif
diff-contract validate --files src/foo.py --sarif
```

GitHub Actions workflow:

```yaml
- uses: yunaremaia/diff-contract@main
  with:
    format: sarif
    sarif-output: diff-contract.sarif

- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: diff-contract.sarif
```

SARIF output includes one rule per violation type. Block violations emit at `error` level, warnings at `warning`.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Clean — no violations |
| 1 | Block violation — file denied, outside allowed scope, or an aggregate limit exceeded with `on_violation: block` |
| 2 | Warning — non-blocking violation (e.g., large diff with `on_violation: warn`) |

## Rules

- **allow**: File globs that are permitted (all others blocked)
- **deny**: File globs that are denied (takes priority)
- **on_violation**: `block` (exit 1) or `warn` (exit 2)
- **max_files** / **max_lines**: optional aggregate size limits (see below)

## Aggregate Limits

Path allow/deny rules constrain *which* files may change. `max_files` and `max_lines` constrain *how large* a change set may be. They are evaluated against the whole diff after per-file rules run.

| Field | Meaning |
|-------|---------|
| `max_files` | Maximum number of changed files in the diff |
| `max_lines` | Maximum total changed lines (`added + deleted` from `git diff --numstat`) |

A rule may set either field, both, or neither. Limits are omitted by default (no size budget). When a limit is exceeded, the engine records an aggregate violation on the synthetic path `<aggregate>` and applies that rule's `on_violation`:

- `on_violation: block` — fail the check (exit code **1**). Use this to stop AI agents or CI from landing oversized diffs.
- `on_violation: warn` — report the overshoot but continue (exit code **2** if there are no block violations). Use this as a PR-size nudge.

Typical uses:

- Cap feature work so an agent cannot rewrite half the tree while implementing one ticket.
- Keep documentation or bugfix rules tight even when the path globs are broad.
- Warn on large diffs without blocking hotfixes.

Limits are compared against the **entire** change list, not only files that match that rule's `allow`/`deny` globs. A rule that only sets `max_files` / `max_lines` (no path patterns) is a global size guard.

### Example

```yaml
# .diffcontract.yml
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
      - "tests/features/**"
    max_files: 15
    max_lines: 400
    on_violation: block

  - name: "Large diff warning"
    max_files: 20
    max_lines: 600
    on_violation: warn
```

In this contract:

- Changes under `src/core/**` or `*.env` are blocked.
- Feature-area diffs may proceed only if they stay within 15 files and 400 lines; exceeding either budget is a **block** (exit 1).
- Any diff larger than 20 files or 600 lines also produces a **warning** (exit 2 when nothing is blocked).

See [`examples/strict.yml`](examples/strict.yml) for a fuller contract that combines deny rules with per-rule size budgets.

## License

MIT

# diff-contract

![CI](https://github.com/yunaremaia/diff-contract/actions/workflows/ci.yml/badge.svg)
