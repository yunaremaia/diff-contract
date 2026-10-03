"""Tests for diff-contract — contract parsing and validation."""

import pytest
import yaml

from diff_contract.contract import ContractParser, ContractRule, ViolationSeverity
from diff_contract.engine import DiffCalculator, RulesEngine, Violation


class TestContractParser:
    def test_parse_minimal_contract(self):
        yaml_content = """
version: 1
rules:
  - name: "Allow src"
    allow: ["src/**"]
    on_violation: block
"""
        data = yaml.safe_load(yaml_content)
        parser = ContractParser()
        contract = parser.parse(data)

        assert len(contract.rules) == 1
        assert contract.rules[0].name == "Allow src"
        assert contract.rules[0].on_violation == ViolationSeverity.BLOCK

    def test_parse_with_deny(self):
        yaml_content = """
version: 1
rules:
  - name: "Block core"
    deny: ["src/core/**"]
    on_violation: block
"""
        data = yaml.safe_load(yaml_content)
        parser = ContractParser()
        contract = parser.parse(data)

        assert len(contract.rules) == 1
        assert contract.rules[0].deny == ("src/core/**",)

    def test_parse_invalid_severity_raises_value_error(self):
        """An unknown on_violation value must raise, not silently default to block.

        Silently coercing a typo to 'block' would either block a diff the author
        expected to be a warning, or — worse — accept a typo like 'blocks' as a
        rule that never matches the intended severity.
        """
        data = yaml.safe_load(
            """
version: 1
rules:
  - name: "Typo severity"
    allow: ["docs/**"]
    on_violation: blocks
"""
        )
        parser = ContractParser()
        with pytest.raises(ValueError) as exc_info:
            parser.parse(data)
        message = str(exc_info.value)
        assert "blocks" in message
        # The error must list the valid values so the typo is fixable.
        assert "block" in message and "warn" in message and "info" in message

    def test_parse_warn_severity(self):
        yaml_content = """
version: 1
rules:
  - name: "Docs only"
    allow: ["docs/**"]
    on_violation: warn
"""
        data = yaml.safe_load(yaml_content)
        parser = ContractParser()
        contract = parser.parse(data)

        assert contract.rules[0].on_violation == ViolationSeverity.WARN

    def test_parse_empty_contract(self):
        yaml_content = """
version: 1
rules: []
"""
        data = yaml.safe_load(yaml_content)
        parser = ContractParser()
        contract = parser.parse(data)

        assert len(contract.rules) == 0


class TestRulesEngine:
    def test_allow_only_matching_files(self):
        """Files matching allow should not be violations."""
        rule = ContractRule(
            name="Allow src",
            allow=["src/**"],
            deny=[],
            on_violation=ViolationSeverity.BLOCK,
        )
        engine = RulesEngine([rule])
        violations = engine.check(["src/app.py", "src/utils.py"])
        assert len(violations) == 0

    def test_allow_blocks_non_matching_files(self):
        """Files not matching allow should be violations."""
        rule = ContractRule(
            name="Allow src",
            allow=["src/**"],
            deny=[],
            on_violation=ViolationSeverity.BLOCK,
        )
        engine = RulesEngine([rule])
        violations = engine.check(["tests/test_app.py", "docs/README.md"])
        assert len(violations) == 2
        assert violations[0].severity == ViolationSeverity.BLOCK

    def test_deny_blocks_matching_files(self):
        """Files matching deny should be violations."""
        rule = ContractRule(
            name="Block core",
            allow=[],
            deny=["src/core/**"],
            on_violation=ViolationSeverity.BLOCK,
        )
        engine = RulesEngine([rule])
        violations = engine.check(["src/core/db.py"])
        assert len(violations) == 1
        assert violations[0].severity == ViolationSeverity.BLOCK

    def test_deny_allows_other_files(self):
        """Files not matching deny should not be violations."""
        rule = ContractRule(
            name="Block core",
            allow=[],
            deny=["src/core/**"],
            on_violation=ViolationSeverity.BLOCK,
        )
        engine = RulesEngine([rule])
        violations = engine.check(["src/app.py", "src/utils.py"])
        assert len(violations) == 0

    def test_warn_severity(self):
        """Warn severity should not block but should report."""
        rule = ContractRule(
            name="Docs only",
            allow=["docs/**"],
            deny=[],
            on_violation=ViolationSeverity.WARN,
        )
        engine = RulesEngine([rule])
        violations = engine.check(["src/app.py"])
        assert len(violations) == 1
        assert violations[0].severity == ViolationSeverity.WARN

    def test_multiple_rules_first_match_wins(self):
        """First matching rule determines outcome."""
        rule1 = ContractRule(
            name="Block core",
            allow=[],
            deny=["src/core/**"],
            on_violation=ViolationSeverity.BLOCK,
        )
        rule2 = ContractRule(
            name="Allow src",
            allow=["src/**"],
            deny=[],
            on_violation=ViolationSeverity.BLOCK,
        )
        engine = RulesEngine([rule1, rule2])
        violations = engine.check(["src/core/db.py"])
        assert len(violations) == 1
        assert violations[0].severity == ViolationSeverity.BLOCK

    def test_deny_violation_suppresses_warn_from_other_rule(self):
        """Deny takes precedence: a BLOCK deny drops the WARN on the same file.

        The engine's contract (engine.py:48-49, README "deny ... takes priority")
        says that when any deny rule matches, only the blocking violations are
        reported. Without this, a denied file also emits a noisy WARN and callers
        that branch on "any warnings present" mis-classify the diff.
        """
        deny_block = ContractRule(
            name="Block core",
            allow=[],
            deny=["src/core/**"],
            on_violation=ViolationSeverity.BLOCK,
        )
        allow_warn = ContractRule(
            name="Warn on scope",
            allow=["src/features/**"],
            deny=[],
            on_violation=ViolationSeverity.WARN,
        )
        engine = RulesEngine([deny_block, allow_warn])

        # src/core/db.py matches the deny rule AND falls outside the warn rule's allow.
        violations = engine.check(["src/core/db.py"])

        assert len(violations) == 1, f"expected only the deny violation, got {violations}"
        assert violations[0].rule == "Block core"
        assert violations[0].severity == ViolationSeverity.BLOCK
        # The suppressed violation's message must not leak into the output.
        assert not any(v.rule == "Warn on scope" for v in violations)

    def test_deny_precedence_reports_every_matching_deny_rule(self):
        """Precedence filters by severity — it must not collapse to one violation.

        Both deny rules match the same file, so both blocking violations belong in
        the report; a "report only the first match" regression would hide the second
        rule's finding and understate the blast radius of the change.
        """
        rule1 = ContractRule(
            name="Block core",
            allow=[],
            deny=["src/core/**"],
            on_violation=ViolationSeverity.BLOCK,
        )
        rule2 = ContractRule(
            name="Block secrets",
            allow=[],
            deny=["src/core/**", "*.key"],
            on_violation=ViolationSeverity.BLOCK,
        )
        engine = RulesEngine([rule1, rule2])

        violations = engine.check(["src/core/db.py"])

        assert {v.rule for v in violations} == {"Block core", "Block secrets"}
        assert all(v.severity == ViolationSeverity.BLOCK for v in violations)

    def test_warn_alone_is_still_reported_without_a_deny_match(self):
        """Precedence only suppresses when a deny actually matches.

        Guards against over-broad suppression: when nothing denies the file, the
        WARN must survive, otherwise warning-only contracts go silent.
        """
        deny_block = ContractRule(
            name="Block core",
            allow=[],
            deny=["src/core/**"],
            on_violation=ViolationSeverity.BLOCK,
        )
        allow_warn = ContractRule(
            name="Warn on scope",
            allow=["src/features/**"],
            deny=[],
            on_violation=ViolationSeverity.WARN,
        )
        engine = RulesEngine([deny_block, allow_warn])

        violations = engine.check(["src/app.py"])  # no deny match

        assert len(violations) == 1
        assert violations[0].rule == "Warn on scope"
        assert violations[0].severity == ViolationSeverity.WARN

    def test_deny_violation_message_identifies_file_and_rule(self):
        """The deny message must name the offending file and the rule that caught it.

        This message is the whole diagnostic the user sees; a regression that drops
        either identifier leaves an unactionable violation.
        """
        rule = ContractRule(
            name="Block core",
            allow=[],
            deny=["src/core/**"],
            on_violation=ViolationSeverity.BLOCK,
        )
        violations = RulesEngine([rule]).check(["src/core/db.py"])

        assert len(violations) == 1
        assert "src/core/db.py" in violations[0].message
        assert "Block core" in violations[0].message

    def test_empty_diff_no_violations(self):
        """Empty diff should produce no violations."""
        rule = ContractRule(
            name="Allow src",
            allow=["src/**"],
            deny=[],
            on_violation=ViolationSeverity.BLOCK,
        )
        engine = RulesEngine([rule])
        violations = engine.check([])
        assert len(violations) == 0

    def test_glob_pattern_matching(self):
        """Glob patterns should match correctly."""
        rule = ContractRule(
            name="Block env files",
            allow=[],
            deny=["*.env", "*.env.*"],
            on_violation=ViolationSeverity.BLOCK,
        )
        engine = RulesEngine([rule])
        violations = engine.check([".env", "prod.env", "config.env.local"])
        assert len(violations) == 3


class TestDiffCalculator:
    def test_empty_diff(self):
        """Empty diff should return empty list."""
        calc = DiffCalculator(base_branch="main")
        assert calc.base_branch == "main"


class TestViolation:
    def test_violation_str_block(self):
        """Block violation should show severity and file."""
        v = Violation(
            file="src/core/db.py",
            severity=ViolationSeverity.BLOCK,
            rule="Block core",
            message="File 'src/core/db.py' is denied by rule 'Block core'",
        )
        assert "BLOCK" in str(v)
        assert "src/core/db.py" in str(v)

    def test_violation_str_warn(self):
        """Warn violation should show severity and file."""
        v = Violation(
            file="src/app.py",
            severity=ViolationSeverity.WARN,
            rule="Docs only",
            message="File 'src/app.py' not allowed by rule 'Docs only'",
        )
        assert "WARN" in str(v)
        assert "src/app.py" in str(v)
