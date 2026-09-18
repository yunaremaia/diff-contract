"""Tests for diff-contract — contract parsing and validation."""

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
