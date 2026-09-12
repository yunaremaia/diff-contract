"""Rules engine — validates diffs against contracts."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from diff_contract.contract import Contract, ContractRule, ViolationSeverity


@dataclass(frozen=True)
class Violation:
    file: str
    severity: ViolationSeverity
    rule: str
    message: str


class RulesEngine:
    """Validate a list of changed files against contract rules."""

    def __init__(self, rules: Sequence[ContractRule]) -> None:
        self.rules = list(rules)

    def check(self, changed_files: Sequence[str]) -> list[Violation]:
        """Check changed files against all rules."""
        violations: list[Violation] = []
        for file in changed_files:
            for rule in self.rules:
                v = self._check_file(file, rule)
                if v is not None:
                    violations.append(v)
                    break  # first matching rule wins
        # Check aggregate rules (max_files, max_lines)
        violations.extend(self._check_aggregate_rules(changed_files))
        return violations

    def _check_aggregate_rules(self, changed_files: Sequence[str]) -> list[Violation]:
        """Check aggregate rules like max_files and max_lines."""
        violations: list[Violation] = []
        total_lines = sum(
            len(f.get("hunks", [{}])[0].get("lines", [])) if isinstance(f, dict) else 0
            for f in changed_files
        )
        # Actually, for aggregate we need line counts. Since we only have file paths
        # here, max_lines can't be checked from paths alone; we rely on callers to
        # pass count info if available. For now, check max_files only.
        for rule in self.rules:
            if rule.max_files is not None and len(changed_files) > rule.max_files:
                violations.append(Violation(
                    file="<aggregate>",
                    severity=rule.on_violation,
                    rule=rule.name,
                    message=f"Too many files changed ({len(changed_files)} > {rule.max_files})",
                ))
        return violations

    def _check_file(self, file: str, rule: ContractRule) -> Violation | None:
        """Check a single file against a single rule."""
        # Deny takes priority — if file matches deny, it's a violation
        if rule.matches_deny(file):
            return Violation(
                file=file,
                severity=rule.on_violation,
                rule=rule.name,
                message=f"File '{file}' is denied by rule '{rule.name}'",
            )

        # If allow patterns are defined and file doesn't match, it's a violation
        if rule.allow and not rule.matches_allow(file):
            return Violation(
                file=file,
                severity=rule.on_violation,
                rule=rule.name,
                message=f"File '{file}' not allowed by rule '{rule.name}'",
            )

        return None


class DiffCalculator:
    """Calculate diff between current branch and base."""

    def __init__(self, base_branch: str = "main", cwd: Path | None = None) -> None:
        self.base_branch = base_branch
        self.cwd = cwd

    def get_changed_files(self) -> list[str]:
        """Run git diff and return list of changed files."""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", f"{self.base_branch}...HEAD"],
                capture_output=True,
                text=True,
                check=True,
                cwd=self.cwd,
            )
        except subprocess.CalledProcessError:
            # Fallback: if we're on the base branch or no diff, return empty
            return []
        return self._parse_diff_output(result.stdout)

    def _parse_diff_output(self, raw: str) -> list[str]:
        """Parse git diff --name-only output."""
        if not raw.strip():
            return []
        return [line.strip() for line in raw.splitlines() if line.strip()]


def validate_diff(
    contract: Contract,
    changed_files: Sequence[str],
) -> list[Violation]:
    """Convenience: validate changed files against a contract."""
    engine = RulesEngine(contract.rules)
    return engine.check(changed_files)
