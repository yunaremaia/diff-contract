"""Contract parser — reads and validates .diffcontract.yml files."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ViolationSeverity(enum.Enum):
    BLOCK = "block"
    WARN = "warn"
    INFO = "info"


@dataclass(frozen=True)
class ContractRule:
    name: str
    allow: tuple[str, ...] = ()
    deny: tuple[str, ...] = ()
    on_violation: ViolationSeverity = ViolationSeverity.BLOCK
    max_files: int | None = None
    max_lines: int | None = None

    def matches_allow(self, file_path: str) -> bool:
        """Return True if file matches any allow glob."""
        import fnmatch

        return any(fnmatch.fnmatch(file_path, pattern) for pattern in self.allow)

    def matches_deny(self, file_path: str) -> bool:
        """Return True if file matches any deny glob."""
        import fnmatch

        return any(fnmatch.fnmatch(file_path, pattern) for pattern in self.deny)


@dataclass(frozen=True)
class Contract:
    version: int
    rules: tuple[ContractRule, ...] = ()


def _as_pattern_tuple(raw: Any, field: str, index: int) -> tuple[str, ...]:
    """Parse and validate an allow/deny field as a list of glob strings.

    Raises ValueError with a clear message if the field is not a list of strings,
    so that a bare YAML string (which tuple() silently splits into characters)
    produces a readable error instead of a silent no-op.
    """
    value = raw.get(field, [])
    if value is None:
        return ()
    if isinstance(value, str):
        raise ValueError(
            f"Invalid '{field}' value at rule {index}: expected a list of glob "
            f"strings, got the string {value!r}. Did you mean:\n"
            f"  {field}:\n    - \"{value}\""
        )
    if not isinstance(value, (list, tuple)):
        raise ValueError(
            f"Invalid '{field}' value at rule {index}: expected a list of glob "
            f"strings, got {type(value).__name__}"
        )
    bad = [p for p in value if not isinstance(p, str)]
    if bad:
        raise ValueError(
            f"Invalid '{field}' entry at rule {index}: expected a string, "
            f"got {bad!r}"
        )
    return tuple(value)


class ContractParser:
    """Parse contract from YAML dict."""

    def parse(self, data: dict[str, Any]) -> Contract:
        version = data.get("version", 1)
        raw_rules = data.get("rules", [])
        rules: list[ContractRule] = []
        for i, raw_rule in enumerate(raw_rules):
            rule = self._parse_rule(raw_rule, index=i)
            rules.append(rule)
        return Contract(version=version, rules=tuple(rules))

    def _parse_rule(self, raw: dict[str, Any], index: int) -> ContractRule:
        name = raw.get("name", f"rule-{index}")
        severity_str = raw.get("on_violation", "block")
        try:
            severity = ViolationSeverity(severity_str)
        except ValueError:
            valid = [s.value for s in ViolationSeverity]
            raise ValueError(
                f"Invalid on_violation value '{severity_str}' at rule {index}. "
                f"Valid values: {valid}"
            )

        allow = _as_pattern_tuple(raw, "allow", index)
        deny = _as_pattern_tuple(raw, "deny", index)
        max_files = raw.get("max_files")
        max_lines = raw.get("max_lines")

        return ContractRule(
            name=name,
            allow=allow,
            deny=deny,
            on_violation=severity,
            max_files=max_files,
            max_lines=max_lines,
        )

    def parse_file(self, path: Path) -> Contract:
        """Parse contract from YAML file."""
        text = path.read_text()
        data = yaml.safe_load(text) or {}
        return self.parse(data)


def load_contract(path: Path) -> Contract:
    """Convenience: load contract from path."""
    parser = ContractParser()
    return parser.parse_file(path)
