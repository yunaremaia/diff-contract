"""Rules engine — validates diffs against contracts."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, Union

from diff_contract.contract import Contract, ContractRule, ViolationSeverity


@dataclass(frozen=True)
class Violation:
    file: str
    severity: ViolationSeverity
    rule: str
    message: str


# A file entry can be a raw path (from --files CLI arg) or a change dict
FileEntry = Union[str, dict]


def _extract_path(entry: FileEntry) -> str:
    """Extract file path from a FileEntry (str or dict)."""
    if isinstance(entry, dict):
        return entry.get("path", "")
    return entry


def _extract_lines(entry: FileEntry) -> int:
    """Extract changed line count from a FileEntry."""
    if isinstance(entry, dict):
        return entry.get("lines", 0)
    return 0


class RulesEngine:
    """Validate a list of changed files against contract rules."""

    def __init__(self, rules: Sequence[ContractRule]) -> None:
        self.rules = list(rules)

    def check(self, changed_files: Sequence[FileEntry]) -> list[Violation]:
        """Check changed files against all rules.

        All rules are evaluated for each file. Deny rules take precedence
        over allow rules — if any deny rule matches, the file is blocked.
        """
        violations: list[Violation] = []
        for file in changed_files:
            path = _extract_path(file)
            file_violations: list[Violation] = []
            has_deny = False
            for rule in self.rules:
                v = self._check_file(path, rule)
                if v is not None:
                    file_violations.append(v)
                    if v.severity == ViolationSeverity.BLOCK:
                        has_deny = True
            # Deny rules take precedence — if any deny matched, report only denies
            if has_deny:
                violations.extend(v for v in file_violations if v.severity == ViolationSeverity.BLOCK)
            else:
                violations.extend(file_violations)
        # Check aggregate rules (max_files, max_lines)
        violations.extend(self._check_aggregate_rules(changed_files))
        return violations

    def _check_aggregate_rules(self, changed_files: Sequence[FileEntry]) -> list[Violation]:
        """Check aggregate rules like max_files and max_lines."""
        violations: list[Violation] = []
        total_files = len(changed_files)
        total_lines = sum(_extract_lines(f) for f in changed_files)
        for rule in self.rules:
            if rule.max_files is not None and total_files > rule.max_files:
                violations.append(
                    Violation(
                        file="<aggregate>",
                        severity=rule.on_violation,
                        rule=rule.name,
                        message=f"Too many files changed ({total_files} > {rule.max_files})",
                    )
                )
            if rule.max_lines is not None and total_lines > rule.max_lines:
                violations.append(
                    Violation(
                        file="<aggregate>",
                        severity=rule.on_violation,
                        rule=rule.name,
                        message=f"Too many lines changed ({total_lines} > {rule.max_lines})",
                    )
                )
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


class GitDiffError(Exception):
    """Raised when git diff command fails."""

    def __init__(self, message: str, returncode: int = 1, stderr: str = "") -> None:
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


class DiffCalculator:
    """Calculate diff between current branch and base."""

    def __init__(self, base_branch: str = "main", cwd: Path | None = None) -> None:
        self.base_branch = base_branch
        self.cwd = cwd

    def get_changed_files(self) -> list[dict]:
        """Run git diff and return list of file change dicts with line counts.

        Raises:
            GitDiffError: If git diff fails or git executable is not found.
        """
        try:
            result = subprocess.run(
                ["git", "--no-pager", "diff", "--numstat", f"{self.base_branch}...HEAD"],
                capture_output=True,
                text=True,
                check=True,
                cwd=self.cwd,
            )
        except subprocess.CalledProcessError as e:
            err_msg = (
                e.stderr.strip()
                if e.stderr
                else f"git command failed with exit code {e.returncode}"
            )
            raise GitDiffError(
                f"git diff failed: {err_msg}",
                returncode=e.returncode,
                stderr=e.stderr or "",
            ) from e
        except FileNotFoundError as e:
            raise GitDiffError("git executable not found", returncode=127) from e
        return self._parse_numstat(result.stdout)

    def _parse_numstat(self, raw: str) -> list[dict]:
        """Parse git diff --numstat output into list of change dicts."""
        if not raw.strip():
            return []
        changes = []
        for line in raw.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                try:
                    added = int(parts[0])
                except ValueError:
                    added = 0  # binary files show "-"
                try:
                    deleted = int(parts[1])
                except ValueError:
                    deleted = 0
                path = parts[2]
                changes.append(
                    {
                        "path": path,
                        "added": added,
                        "deleted": deleted,
                        "lines": added + deleted,
                    }
                )
        return changes


def validate_diff(
    contract: Contract,
    changed_files: Sequence[FileEntry],
) -> list[Violation]:
    """Convenience: validate changed files against a contract."""
    engine = RulesEngine(contract.rules)
    return engine.check(changed_files)
