# Rules

A contract is a list of rules. Each rule is evaluated against **every** changed
file, and each rule independently decides whether that file is acceptable.

## Per-file evaluation

For one file and one rule, in this order:

1. If the path matches any of the rule's `deny` globs → violation,
   `"File 'PATH' is denied by rule 'NAME'"`.
2. Else, if the rule has `allow` globs and the path matches none of them →
   violation, `"File 'PATH' not allowed by rule 'NAME'"`.
3. Else → no violation.

A rule with no `allow` and no `deny` globs produces no per-file violations. It
can still carry `max_files` / `max_lines` and act as a global size guard.

## Deny wins across rules

If a file produced at least one `block` violation, only `block` violations are
reported for that file — `warn` violations from other matching rules are
dropped. A `deny` hit on a `block` rule therefore silences the accompanying
`not allowed` noise from a `warn` rule.

A single file can still produce several `block` violations when two `block`
rules both match it. Given `deny: ["src/core/**"]` with `on_violation: block`
and `allow: ["src/features/**"]` with `on_violation: block`:

```
✗ 2 violation(s):
  🔴 [BLOCK] File 'src/core/x.py' is denied by rule 'Block core changes'
  🔴 [BLOCK] File 'src/core/x.py' not allowed by rule 'Allow feature X'
```

## Glob semantics

Patterns are matched with Python's
[`fnmatch`](https://docs.python.org/3/library/fnmatch.html), **not** gitignore
syntax. The differences that matter:

| Pattern | Matches | Does not match |
|---------|---------|----------------|
| `src/*` | `src/a.py`, `src/a/b/c.py` | `other/a.py` |
| `src/**` | identical to `src/*` | — |
| `*.env` | `.env`, `config/.env` | `env.example` |
| `*.py` | `src/diff_contract/cli.py` | `README.md` |
| `.github/workflows/*.yml` | `.github/workflows/ci.yml` | `.github/workflows/sub/ci.yml` |

Three consequences worth internalising:

- **`*` crosses `/`.** There is no "one level only" wildcard. `src/*` matches
  `src/a/b/c.py` just as `src/**` does — writing `**` does not buy you
  anything.
- **A bare `*.ext` matches at any depth.** `*.py` covers every Python file in
  the repository, including `src/`.
- **Matching is case-sensitive** on Linux and macOS. `*.MD` does not match
  `README.md`.

There is no negation syntax (`!`), no `**` "descend everywhere" operator, and no
directory-only pattern.

## Aggregate limits

`max_files` and `max_lines` constrain how large the diff is, not which files it
touches. They are checked once, against the **entire** change list, after all
per-file rules have run.

| Field | Meaning |
|-------|---------|
| `max_files` | Maximum number of changed files |
| `max_lines` | Maximum total changed lines — `added + deleted` from `git diff --numstat` |

Both are optional; a rule may set either, both, or neither. When a limit is
exceeded the violation is recorded on the synthetic path `<aggregate>`:

```
✗ 2 violation(s):
  🔴 [BLOCK] File 'nope.py' not allowed by rule 'Only md'
  🟡 [WARN] Too many lines changed (9 > 2)
```

```json
{
  "file": "<aggregate>",
  "severity": "warn",
  "rule": "Size guard",
  "message": "Too many lines changed (9 > 2)"
}
```

The rule's `on_violation` decides whether an overshoot blocks or warns. A rule
with only `max_files` / `max_lines` and no path globs is a global size guard —
the usual way to add "and keep the whole change small" on top of the per-file
rules.

!!! warning "`max_lines` needs a real diff"
    Line counts come from `git diff --numstat`, so `max_lines` is only enforced
    by `check`. Under `validate` each path counts as `0` changed lines and the
    limit can never trip. `max_files` works in both commands.

## `on_violation`

| Value | Reported as | Exit code contribution |
|-------|-------------|------------------------|
| `block` | `[BLOCK]`, SARIF `error` | `1` |
| `warn` | `[WARN]`, SARIF `warning` | `2` |
| `info` | `[INFO]`, SARIF `warning` | none — exits `0` |

`info` violations are still listed and still set `clean: false` in JSON output;
they simply never fail a run. Use them for advice you want visible in CI logs
without blocking merges.

Any other value is rejected at parse time with
`Invalid on_violation value '...' at rule N. Valid values: ['block', 'warn', 'info']`.

## Worked example

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

Reading it:

- Anything under `src/core/` or any `.env` file at any depth is **blocked**.
- Every other file must be under `src/features/` or `tests/features/` —
  anything else is **blocked** by "Feature development".
- If the diff exceeds 15 files or 400 changed lines, that is a **block**.
- If it exceeds 20 files or 600 lines, that is a **warning** (exit `2` when
  nothing is blocked).

Because `*.env` matches at any depth, it covers `apps/api/.env` as well as a
top-level `.env`.

## Next steps

- [Configuration](configuration.md) — the full contract file format
- [Usage](usage.md) — commands and exit codes
