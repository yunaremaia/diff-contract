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
diff-contract init    # creates .diffcontract.yml in current directory
```

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
| 1 | Block violation — file denied or outside allowed scope |
| 2 | Warning — non-blocking violation (e.g., large diff) |

## Rules

- **allow**: File globs that are permitted (all others blocked)
- **deny**: File globs that are denied (takes priority)
- **on_violation**: `block` (exit 1) or `warn` (exit 2)

## License

MIT
