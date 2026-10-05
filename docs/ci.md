# CI

`diff-contract` exits `1` on a block violation, so the simplest gate is any step
that fails on a non-zero exit code.

```yaml
- run: pip install diff-contract
- run: diff-contract check --base origin/main
```

Use `--base origin/main` in CI: `actions/checkout` gives you a shallow clone,
so a plain `main` may not exist. The shipped action already sets `fetch-depth: 0`
for exactly this reason.

## GitHub Action

The repo ships a composite action at
[`action.yml`](https://github.com/yunaremaia/diff-contract/blob/main/action.yml).

```yaml
name: diff-contract
on: pull_request

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: yunaremaia/diff-contract@main
```

### Inputs

| Input | Default | Meaning |
|-------|---------|---------|
| `contract` | `.diffcontract.yml` | Path to the contract |
| `base` | `main` | Base branch to diff against |
| `format` | `text` | `text`, `json`, or `sarif` |
| `sarif-output` | `diff-contract.sarif` | Where the SARIF file is written |
| `github-token` | `${{ github.token }}` | Token passed to the SARIF upload |

The action checks out the repository itself with `fetch-depth: 0`, sets up
Python 3.11, and installs the published package from PyPI with
`pip install diff-contract`. It does not run the code in your checkout — if you
are testing an unreleased change, run the CLI directly instead.

Because `format: sarif` exits `1` when the diff is blocked, add
`continue-on-error: true` if you want Code Scanning to receive the findings
even on a failing run. The action's upload step already carries `always()`.

Pin the action to a tag (`@v0.1.2`) rather than `@main` once you rely on it.

## GitHub Code Scanning

With `format: sarif` the action writes the SARIF file and uploads it with
`github/codeql-action/upload-sarif`, so findings appear in the Security tab
alongside CodeQL's.

```yaml
- uses: yunaremaia/diff-contract@main
  with:
    format: sarif
    sarif-output: diff-contract.sarif
```

Each contract rule becomes one SARIF rule with id `diff-contract/<rule name>`.
`block` violations are reported at `error` level, `warn` and `info` at
`warning`.

Uploading manually is the same two steps:

```yaml
- run: pip install diff-contract
- run: diff-contract check --sarif > diff-contract.sarif
- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: diff-contract.sarif
```

The emitted document is SARIF 2.1.0:

```json
{
  "version": "2.1.0",
  "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "diff-contract",
          "version": "0.1.0",
          "informationUri": "https://github.com/yunaremaia/diff-contract",
          "rules": [
            {
              "id": "diff-contract/Feature development",
              "name": "Feature development",
              "shortDescription": { "text": "Contract rule: Feature development" },
              "defaultConfiguration": { "level": "error" }
            }
          ]
        }
      },
      "results": [
        {
          "ruleId": "diff-contract/Feature development",
          "level": "error",
          "message": { "text": "File 'src/app.py' not allowed by rule 'Feature development'" },
          "locations": [
            {
              "physicalLocation": {
                "artifactLocation": { "uri": "src/app.py" }
              }
            }
          ]
        }
      ]
    }
  ]
}
```

!!! note "The SARIF driver version is not the package version"
    `violations_to_sarif()` takes its `tool_version` from a default argument
    rather than the installed metadata, so the `driver.version` field above
    reads `0.1.0` even on a newer release. `diff-contract --version` is
    accurate; the SARIF field is not. Cosmetic, but do not use it to pin
    anything.

## Pre-commit hook

The repo ships a hook definition in
[`.pre-commit-hooks.yaml`](https://github.com/yunaremaia/diff-contract/blob/main/.pre-commit-hooks.yaml).

```yaml
repos:
  - repo: https://github.com/yunaremaia/diff-contract
    rev: v0.1.2
    hooks:
      - id: diff-contract
```

The hook only fires on files matching
`\.(py|js|ts|go|rs|java|rb|yml|yaml|toml|json|md|txt|sh)$`.

!!! warning "Known issue in the shipped hook definition"
    As published, the hook's `entry` is `diff-contract check`, and pre-commit
    appends the staged filenames as **positional** arguments. `check` accepts
    file paths only through `--files`, so the hook fails with
    `error: unrecognized arguments: ...` and exit code `2` on any run that has
    matching files staged.

    Work around it in your own `.pre-commit-config.yaml` until the shipped
    definition is fixed:

    ```yaml
    repos:
      - repo: https://github.com/yunaremaia/diff-contract
        rev: v0.1.2
        hooks:
          - id: diff-contract
            entry: diff-contract check --contract .diffcontract.yml --files
    ```

    With that override the hook passes the staged paths through `--files` and
    blocks the commit on a `block` violation.

## Testing the contract itself

Because the hook and the action both run the same rules, a contract that is too
strict shows up as noise long before it blocks anyone. Check it against a known
diff before wiring it into a required check:

```bash
git checkout -b contract-tuning
# make a handful of representative changes
diff-contract check --output json
```

## Next steps

- [Configuration](configuration.md) — the contract file format
- [Rules](rules.md) — deny precedence and size limits
- [Usage](usage.md) — exit codes
