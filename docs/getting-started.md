# Getting Started

## Install

```bash
pip install diff-contract
```

Requires Python 3.10 or newer. Verify the install:

```bash
diff-contract --version
```

```
diff-contract 0.1.2
```

## Create a contract

`init` writes a starter `.diffcontract.yml` in the current directory. It never
overwrites an existing file — if one is already there it prints a warning and
exits `1`.

```bash
diff-contract init
```

```
✓ Created .diffcontract.yml (template: python)
```

Templates: `python` (default), `react`, `django`, `rust`, `docs`. See
[init templates](configuration.md#init-templates).

Alternatively, write the file yourself:

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

## Check your branch

`check` runs `git diff --numstat main...HEAD` and validates every changed path.
The default base branch is `main`:

```bash
diff-contract check
```

If the base branch has a different name:

```bash
diff-contract check --base develop
```

The comparison is `base...HEAD` (three dots), so only commits on your branch
count — changes landed on `main` after the branch point are excluded. Your
working tree is **not** included: uncommitted edits do not affect the result.

## Read the output

A clean diff:

```
✓ Diff is clean — no contract violations
```

Exit code `0`.

A violation:

```
✗ 2 violation(s):
  🔴 [BLOCK] File 'src/core/x.py' is denied by rule 'Block core changes'
  🔴 [BLOCK] File 'src/core/x.py' not allowed by rule 'Allow feature X'
```

Exit code `1`. Both lines are reported because two separate rules matched; the
first is a `deny` match, the second is an `allow` miss.

A warning:

```
✗ 1 violation(s):
  🟡 [WARN] Too many files changed (3 > 2)
```

Exit code `2`.

## Check specific files

To skip git entirely — useful in a hook, a script, or a repo that is not a git
working tree — pass the paths yourself:

```bash
diff-contract validate --files src/app.py tests/test_app.py
```

```
✓ Diff is clean — no contract violations
```

Piping a list works too, one path per line:

```bash
git diff --name-only main...HEAD | diff-contract validate --from-stdin
```

`validate` needs one of `--files` or `--from-stdin`; with neither it prints
`ERROR: Provide --files or --from-stdin` and exits `1`.

## Next steps

- [Usage](usage.md) — every flag, and the exit-code contract
- [Rules](rules.md) — how glob matching and deny precedence actually work
- [Configuration](configuration.md) — every key in the contract file
- [CI](ci.md) — run it on every pull request
