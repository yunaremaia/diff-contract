"""Tests for diff-contract rules engine."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from diff_contract.contract import Contract, ContractRule, ViolationSeverity
from diff_contract.engine import DiffCalculator, GitDiffError, RulesEngine, validate_diff


class TestRulesEngineMaxLines:
    """Tests for max_lines aggregate rule — bug fix for issue #2."""

    def test_max_lines_exceeded_warn(self):
        """When total lines exceed max_lines, emit a violation."""
        rule = ContractRule(
            name="max-lines",
            max_lines=10,
            on_violation=ViolationSeverity.WARN,
        )
        engine = RulesEngine(rules=[rule])
        # Simulate files with line counts
        files = [
            {"path": "a.py", "lines": 6, "added": 4, "deleted": 2},
            {"path": "b.py", "lines": 8, "added": 8, "deleted": 0},
        ]
        violations = engine.check(files)
        # Total lines = 14 > 10 → violation
        assert len(violations) >= 1
        aggregate = [v for v in violations if v.file == "<aggregate>"]
        assert len(aggregate) == 1
        assert "14" in aggregate[0].message
        assert "10" in aggregate[0].message

    def test_max_lines_not_exceeded(self):
        """When total lines are within max_lines, no aggregate violation."""
        rule = ContractRule(
            name="max-lines",
            max_lines=100,
            on_violation=ViolationSeverity.WARN,
        )
        engine = RulesEngine(rules=[rule])
        files = [
            {"path": "a.py", "lines": 5, "added": 5, "deleted": 0},
        ]
        violations = engine.check(files)
        assert not any(v.file == "<aggregate>" for v in violations)

    def test_max_lines_block_severity(self):
        """max_lines violation uses configured severity."""
        rule = ContractRule(
            name="strict-lines",
            max_lines=5,
            on_violation=ViolationSeverity.BLOCK,
        )
        engine = RulesEngine(rules=[rule])
        files = [
            {"path": "x.py", "lines": 10, "added": 10, "deleted": 0},
        ]
        violations = engine.check(files)
        aggregate = [v for v in violations if v.file == "<aggregate>"]
        assert len(aggregate) == 1
        assert aggregate[0].severity == ViolationSeverity.BLOCK

    def test_max_lines_with_string_entries(self):
        """String entries (no line count) should still count as 0 lines."""
        rule = ContractRule(
            name="max-lines",
            max_lines=5,
            on_violation=ViolationSeverity.WARN,
        )
        engine = RulesEngine(rules=[rule])
        files = ["a.py", "b.py"]
        violations = engine.check(files)
        # 0 lines total < 5 → no violation
        assert not any(v.file == "<aggregate>" for v in violations)

    def test_max_files_still_works(self):
        """max_files aggregate rule still functions after fix."""
        rule = ContractRule(
            name="max-files",
            max_files=2,
            on_violation=ViolationSeverity.BLOCK,
        )
        engine = RulesEngine(rules=[rule])
        files = ["a.py", "b.py", "c.py"]
        violations = engine.check(files)
        assert len(violations) == 1
        assert "3" in violations[0].message
        assert "2" in violations[0].message


class TestDiffCalculator:
    """Tests for DiffCalculator."""

    def test_parse_numstat(self):
        """_parse_numstat parses numstat format correctly."""
        calc = DiffCalculator()
        raw = "5\t2\tsrc/main.py\n10\t0\ttests/test.py\n"
        result = calc._parse_numstat(raw)
        assert len(result) == 2
        assert result[0] == {"path": "src/main.py", "added": 5, "deleted": 2, "lines": 7}
        assert result[1] == {"path": "tests/test.py", "added": 10, "deleted": 0, "lines": 10}

    def test_parse_numstat_binary(self):
        """Binary files show '-' for added/deleted."""
        calc = DiffCalculator()
        raw = "-\t-\timage.png\n"
        result = calc._parse_numstat(raw)
        assert result[0] == {"path": "image.png", "added": 0, "deleted": 0, "lines": 0}

    def test_parse_numstat_empty(self):
        """Empty input returns empty list."""
        calc = DiffCalculator()
        assert calc._parse_numstat("") == []
        assert calc._parse_numstat("   \n") == []

    def test_get_changed_files_success(self):
        """get_changed_files returns parsed change dicts on success."""
        calc = DiffCalculator(base_branch="main")
        mock_output = "3\t1\tsrc/file.py\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=mock_output, returncode=0)
            files = calc.get_changed_files()
            assert files == [{"path": "src/file.py", "added": 3, "deleted": 1, "lines": 4}]
            mock_run.assert_called_once_with(
                ["git", "--no-pager", "diff", "--numstat", "main...HEAD"],
                capture_output=True,
                text=True,
                check=True,
                cwd=None,
            )

    def test_get_changed_files_called_process_error_raises_git_diff_error(self):
        """subprocess.CalledProcessError is not swallowed; raises GitDiffError."""
        calc = DiffCalculator(base_branch="invalid-branch")
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=128,
                cmd=["git", "diff"],
                stderr="fatal: ambiguous argument 'invalid-branch...HEAD'",
            )
            with pytest.raises(GitDiffError) as exc_info:
                calc.get_changed_files()
            assert exc_info.value.returncode == 128
            assert "fatal: ambiguous argument 'invalid-branch...HEAD'" in str(exc_info.value)
            assert "fatal: ambiguous argument 'invalid-branch...HEAD'" in exc_info.value.stderr

    def test_get_changed_files_called_process_error_empty_stderr(self):
        """CalledProcessError with empty stderr formats error message with returncode."""
        calc = DiffCalculator(base_branch="invalid-branch")
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=2,
                cmd=["git", "diff"],
                stderr="",
            )
            with pytest.raises(GitDiffError) as exc_info:
                calc.get_changed_files()
            assert exc_info.value.returncode == 2
            assert "git command failed with exit code 2" in str(exc_info.value)

    def test_get_changed_files_file_not_found_raises_git_diff_error(self):
        """FileNotFoundError when git binary missing raises GitDiffError."""
        calc = DiffCalculator(base_branch="main")
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")
            with pytest.raises(GitDiffError) as exc_info:
                calc.get_changed_files()
            assert exc_info.value.returncode == 127
            assert "git executable not found" in str(exc_info.value)

    def test_get_changed_files_real_git_failure_in_non_git_dir(self, tmp_path):
        """Running in a non-git directory raises GitDiffError with git error details."""
        calc = DiffCalculator(base_branch="main", cwd=tmp_path)
        with pytest.raises(GitDiffError) as exc_info:
            calc.get_changed_files()
        assert exc_info.value.returncode != 0
        assert "git diff failed" in str(exc_info.value)


class TestValidateDiff:
    """Tests for validate_diff convenience function."""

    def test_validate_with_dicts(self):
        """validate_diff works with change dicts (from DiffCalculator)."""
        contract = Contract(
            version=1,
            rules=(
                ContractRule(
                    name="max-lines",
                    max_lines=5,
                    on_violation=ViolationSeverity.WARN,
                ),
            ),
        )
        files = [
            {"path": "a.py", "lines": 10, "added": 10, "deleted": 0},
        ]
        violations = validate_diff(contract, files)
        assert len(violations) == 1
        assert "10" in violations[0].message

    def test_validate_with_strings(self):
        """validate_diff still works with plain strings (legacy)."""
        contract = Contract(
            version=1,
            rules=(
                ContractRule(
                    name="max-files",
                    max_files=1,
                    on_violation=ViolationSeverity.BLOCK,
                ),
            ),
        )
        files = ["a.py", "b.py"]
        violations = validate_diff(contract, files)
        assert len(violations) == 1
