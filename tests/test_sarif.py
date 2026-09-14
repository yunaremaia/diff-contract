"""Tests for SARIF output."""

from __future__ import annotations

import json

import pytest

from diff_contract.engine import Violation, ViolationSeverity, RulesEngine
from diff_contract.sarif import violations_to_sarif, sarif_to_string


class TestViolationsToSarif:
    """Test SARIF conversion."""

    def test_empty_violations(self) -> None:
        doc = violations_to_sarif([])
        assert doc["version"] == "2.1.0"
        assert doc["$schema"] == "https://json.schemastore.org/sarif-2.1.0.json"
        assert len(doc["runs"][0]["results"]) == 0
        assert len(doc["runs"][0]["tool"]["driver"]["rules"]) == 0

    def test_block_violation(self) -> None:
        violations = [
            Violation(
                file="src/core/main.py",
                severity=ViolationSeverity.BLOCK,
                rule="Block core changes",
                message="File 'src/core/main.py' is denied by rule 'Block core changes'",
            )
        ]
        doc = violations_to_sarif(violations)
        results = doc["runs"][0]["results"]
        assert len(results) == 1
        assert results[0]["level"] == "error"
        assert results[0]["ruleId"] == "diff-contract/Block core changes"
        assert results[0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "src/core/main.py"

    def test_warn_violation(self) -> None:
        violations = [
            Violation(
                file="src/app.py",
                severity=ViolationSeverity.WARN,
                rule="Large diff warning",
                message="Too many files changed (25 > 20)",
            )
        ]
        doc = violations_to_sarif(violations)
        results = doc["runs"][0]["results"]
        assert len(results) == 1
        assert results[0]["level"] == "warning"

    def test_multiple_violations(self) -> None:
        violations = [
            Violation(
                file="src/core/a.py",
                severity=ViolationSeverity.BLOCK,
                rule="Block core changes",
                message="denied",
            ),
            Violation(
                file="src/core/b.py",
                severity=ViolationSeverity.BLOCK,
                rule="Block core changes",
                message="denied",
            ),
            Violation(
                file="src/app.py",
                severity=ViolationSeverity.WARN,
                rule="Large diff warning",
                message="too many",
            ),
        ]
        doc = violations_to_sarif(violations)
        results = doc["runs"][0]["results"]
        assert len(results) == 3
        # Two unique rules
        rules = doc["runs"][0]["tool"]["driver"]["rules"]
        assert len(rules) == 2

    def test_sarif_to_string(self) -> None:
        violations = [
            Violation(
                file="src/core/main.py",
                severity=ViolationSeverity.BLOCK,
                rule="Block core changes",
                message="denied",
            )
        ]
        doc = violations_to_sarif(violations)
        s = sarif_to_string(doc)
        parsed = json.loads(s)
        assert parsed["version"] == "2.1.0"

    def test_custom_tool_name_version(self) -> None:
        doc = violations_to_sarif([], tool_name="custom-tool", tool_version="1.2.3")
        assert doc["runs"][0]["tool"]["driver"]["name"] == "custom-tool"
        assert doc["runs"][0]["tool"]["driver"]["version"] == "1.2.3"
