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
            severity = ViolationSeverity.BLOCK

        allow = tuple(raw.get("allow", []))
        deny = tuple(raw.get("deny", []))
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
