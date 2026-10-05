# diff-contract API Reference

The Python API is small: parse a contract, hand a file list to the rules engine,
read the violations. The CLI is a thin wrapper over exactly these calls.

## Table of Contents

- [Quick start](#quick-start)
- [`diff_contract`](#diff_contract)
- [`diff_contract.contract`](#diff_contractcontract)
- [`diff_contract.engine`](#diff_contractengine)
- [`diff_contract.sarif`](#diff_contractsarif)

## Quick start

```python
from pathlib import Path

from diff_contract.contract import load_contract
from diff_contract.engine import RulesEngine, ViolationSeverity

contract = load_contract(Path(".diffcontract.yml"))
violations = RulesEngine(contract.rules).check(["src/app.py", "src/core/db.py"])

for v in violations:
    print(v.severity.value, v.rule, v.message)

if any(v.severity is ViolationSeverity.BLOCK for v in violations):
    raise SystemExit(1)
```

`check()` accepts either plain path strings or change dicts. Passing dicts is
what makes `max_lines` work, because only dicts carry line counts:

```python
from diff_contract.contract import load_contract
from diff_contract.engine import DiffCalculator, RulesEngine

changes = DiffCalculator(base_branch="main").get_changed_files()
# [{"path": "src/app.py", "added": 12, "deleted": 3, "lines": 15}, ...]

violations = RulesEngine(load_contract(Path(".diffcontract.yml")).rules).check(changes)
```

## `diff_contract`

Re-exports from `diff_contract/__init__.py`:

| Name | Purpose |
|------|---------|
| `__version__` | Installed version string, e.g. `"0.1.2"`. Falls back to `"0.0.0.dev0"` when running from a source checkout with no install metadata. |
| `GitDiffError` | Raised when the `git diff` invocation fails. |

## `diff_contract.contract`

### `ViolationSeverity`

```python
class ViolationSeverity(enum.Enum):
    BLOCK = "block"
    WARN = "warn"
    INFO = "info"
```

### `ContractRule`

```python
ContractRule(
    name: str,
    allow: tuple[str, ...] = (),
    deny: tuple[str, ...] = (),
    on_violation: ViolationSeverity = ViolationSeverity.BLOCK,
    max_files: int | None = None,
    max_lines: int | None = None,
)
```

A frozen dataclass. `allow` and `deny` are tuples of `fnmatch` globs.

#### `matches_allow(file_path: str) -> bool`

`True` if the path matches any `allow` glob. An empty `allow` tuple returns
`False` — check `rule.allow` before calling it to distinguish "no allow patterns
configured" from "path not allowed".

#### `matches_deny(file_path: str) -> bool`

`True` if the path matches any `deny` glob.

### `Contract`

```python
Contract(version: int, rules: tuple[ContractRule, ...] = ())
```

### `ContractParser`

#### `parse(data: dict) -> Contract`

Parses an already-loaded mapping. Missing `version` defaults to `1`; missing
`rules` defaults to `[]`; a rule with no `name` gets `rule-<index>`.

Raises `ValueError` for a bare-string `allow`/`deny` (the "did you mean a list"
message) and for an unrecognised `on_violation` value.

#### `parse_file(path: Path) -> Contract`

Reads the file and calls `parse()`. An empty file yields an empty contract
rather than an error.

### `load_contract(path: Path) -> Contract`

Convenience wrapper: `ContractParser().parse_file(path)`.

## `diff_contract.engine`

### `Violation`

```python
Violation(
    file: str,
    severity: ViolationSeverity,
    rule: str,
    message: str,
)
```

A frozen dataclass describing one finding. For aggregate-limit breaches, `file`
is the synthetic string `"<aggregate>"`.

### `RulesEngine`

#### `RulesEngine(rules: Sequence[ContractRule]) -> RulesEngine`

#### `check(changed_files: Sequence[FileEntry]) -> list[Violation]`

Evaluates every rule against every entry and returns the violations.

`FileEntry` is either a `str` path or a `dict` with `path` and `lines` keys. A
`str` entry contributes `0` lines, so `max_lines` cannot fire unless the entries
are dicts.

Per rule and file: a `deny` match is a violation; otherwise, if the rule has
`allow` globs and none match, that is a violation. If any rule produced a `BLOCK`
violation for a file, only `BLOCK` violations for that file are returned.

Aggregate `max_files` / `max_lines` checks run after the per-file pass, against
the whole list, and apply each rule's own `on_violation`.

```python
from diff_contract.contract import load_contract
from diff_contract.engine import RulesEngine

engine = RulesEngine(load_contract(Path(".diffcontract.yml")).rules)

engine.check(["src/app.py"])                       # strings: no line data
engine.check([{"path": "src/app.py", "lines": 15}])  # dicts: max_lines applies
```

### `DiffCalculator`

#### `DiffCalculator(base_branch: str = "main", cwd: Path | None = None) -> DiffCalculator`

#### `get_changed_files() -> list[dict]`

Runs `git --no-pager diff --numstat BASE...HEAD` and returns one dict per
changed file:

```python
{"path": "src/app.py", "added": 12, "deleted": 3, "lines": 15}
```

Binary files report `-` in `--numstat`; those are parsed as `0` added and `0`
deleted, so binary changes contribute nothing to `max_lines`.

Raises `GitDiffError` if git exits non-zero (unknown base branch, not a
repository) or the `git` executable is missing (`returncode == 127`).

### `GitDiffError`

```python
GitDiffError(message: str, returncode: int = 1, stderr: str = "")
```

Carries the underlying git exit code and stderr.

### `validate_diff`

```python
validate_diff(contract: Contract, changed_files: Sequence[FileEntry]) -> list[Violation]
```

Convenience wrapper: `RulesEngine(contract.rules).check(changed_files)`.

## `diff_contract.sarif`

### `violations_to_sarif`

```python
violations_to_sarif(
    violations: list[Violation],
    tool_name: str = "diff-contract",
    tool_version: str = "0.1.0",
) -> dict
```

Converts violations to a SARIF 2.1.0 document. Each distinct rule name becomes
one entry in `driver.rules` with id `diff-contract/<name>`; `block` maps to
`error`, everything else to `warning`.

!!! note "`tool_version` is not derived from the package"
    It defaults to the literal `"0.1.0"` rather than `diff_contract.__version__`,
    so the emitted `driver.version` does not track releases. Pass
    `tool_version=__version__` explicitly if the value matters.

### `sarif_to_string`

```python
sarif_to_string(sarif_doc: dict) -> str
```

`json.dumps(sarif_doc, indent=2)`.

## Next steps

- [Usage](usage.md) — the same behaviour from the command line
- [Rules](rules.md) — matching and precedence semantics
