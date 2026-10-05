# diff-contract

**Deterministic guardrails for AI-generated diffs — define what files can change, block violations.**

AI coding tools (Cursor, Claude Code, Codex) sometimes modify unrelated files or
drift outside the scope of the task. `diff-contract` sits between the generated
code and your repository and enforces **deterministic** constraints — plain glob
rules in a YAML file, no second AI pass reviewing the first one. It reads the
file list of a diff, matches each path against your rules, and exits non-zero if
anything is out of bounds.

## I want to…

| I want to…                                | Do this                                                            |
|-------------------------------------------|-------------------------------------------------------------------|
| Check my branch against a contract       | [`diff-contract check`](getting-started.md#check-your-branch)      |
| Check specific files, no git needed      | [`diff-contract validate --files`](usage.md#validate)              |
| Write a contract from scratch            | [`diff-contract init`](configuration.md#init-templates)            |
| Understand a violation message           | [Rules](rules.md) — how deny, allow and limits interact            |
| Gate a pull request                      | The shipped GitHub Action — see [CI](ci.md)                        |
| Publish findings to Code Scanning        | `--sarif` — see [CI](ci.md#github-code-scanning)                   |
| Block a commit locally                   | Pre-commit hook — see [CI](ci.md#pre-commit-hook)                  |
| Use it from Python                       | See the [API Reference](api.md)                                    |

## Install

```bash
pip install diff-contract
```

Requires Python 3.10 or newer. The only runtime dependency is PyYAML.

## Sixty-second run

Write a contract:

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

Then check the current branch against `main`:

```bash
diff-contract check
```

```
✗ 2 violation(s):
  🔴 [BLOCK] File 'src/core/x.py' is denied by rule 'Block core changes'
  🔴 [BLOCK] File 'src/core/x.py' not allowed by rule 'Allow feature X'
```

Exit code `1` means a violation blocked the diff; `2` means warnings only.

## How it decides

For every changed file, **all** rules are evaluated. A file that matches a
rule's `deny` globs is a violation; a file that matches none of a rule's `allow`
globs — when that rule has any — is also a violation. Deny wins: if any deny
matched, only deny violations are reported for that file.

Path matching is Python's [`fnmatch`](https://docs.python.org/3/library/fnmatch.html),
not gitignore syntax. `*` crosses directory separators, so `src/*` and `src/**`
behave identically and both match `src/a/b/c.py`. Matching is case-sensitive on
Linux and macOS.

Beyond per-file rules, `max_files` and `max_lines` cap the size of the whole
diff — see [Rules](rules.md#aggregate-limits).

## Where to go next

- [Getting Started](getting-started.md) — install and first run
- [Usage](usage.md) — every flag of `check`, `validate` and `init`
- [Rules](rules.md) — glob semantics, deny precedence, aggregate limits
- [Configuration](configuration.md) — every key in `.diffcontract.yml`
- [CI](ci.md) — GitHub Action, Code Scanning, pre-commit hook
- [API Reference](api.md) — the Python API
- [Example contracts](https://github.com/yunaremaia/diff-contract/tree/main/examples)
  — ready-to-copy files for Python, React, Django, Rust and docs-only projects

## Links

- [Source on GitHub](https://github.com/yunaremaia/diff-contract)
- [Issues](https://github.com/yunaremaia/diff-contract/issues)
- [Changelog](https://github.com/yunaremaia/diff-contract/blob/main/CHANGELOG.md)
- [PyPI](https://pypi.org/project/diff-contract/)
- [Contributing](https://github.com/yunaremaia/diff-contract/blob/main/CONTRIBUTING.md)
- MIT licensed
