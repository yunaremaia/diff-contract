"""Tests for diff-contract CLI."""

import subprocess
import sys


class TestCli:
    def test_check_missing_file(self, tmp_path):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "diff_contract.cli",
                "check",
                "--contract",
                "/nonexistent/file.yaml",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_check_valid_contract(self, tmp_path):
        subprocess.run(
            ["git", "init", "-b", "main"], cwd=str(tmp_path), check=True, capture_output=True
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@test.com",
                "commit",
                "--allow-empty",
                "-m",
                "init",
            ],
            cwd=str(tmp_path),
            check=True,
            capture_output=True,
        )
        contract = tmp_path / "contract.yaml"
        contract.write_text("version: 1\nrules: []\n")
        result = subprocess.run(
            [sys.executable, "-m", "diff_contract.cli", "check", "--contract", str(contract)],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        assert result.returncode == 0

    def test_check_with_files_flag(self, tmp_path):
        contract = tmp_path / "contract.yaml"
        contract.write_text("version: 1\nrules: []\n")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "diff_contract.cli",
                "check",
                "--contract",
                str(contract),
                "--files",
                "test.py",
            ],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        assert result.returncode == 0

    def test_check_git_failure_non_git_repo(self, tmp_path):
        """CLI check fails with exit code 1 when run in a non-git directory."""
        contract = tmp_path / "contract.yaml"
        contract.write_text("version: 1\nrules: []\n")
        result = subprocess.run(
            [sys.executable, "-m", "diff_contract.cli", "check", "--contract", str(contract)],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        assert result.returncode == 1
        assert "ERROR: git diff failed" in result.stderr

    def test_check_git_failure_invalid_branch(self, tmp_path):
        """CLI check fails with exit code 1 when base branch does not exist."""
        subprocess.run(
            ["git", "init", "-b", "main"], cwd=str(tmp_path), check=True, capture_output=True
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@test.com",
                "commit",
                "--allow-empty",
                "-m",
                "init",
            ],
            cwd=str(tmp_path),
            check=True,
            capture_output=True,
        )
        contract = tmp_path / "contract.yaml"
        contract.write_text("version: 1\nrules: []\n")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "diff_contract.cli",
                "check",
                "--contract",
                str(contract),
                "--base",
                "nonexistent-branch-xyz",
            ],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        assert result.returncode == 1
        assert "ERROR: git diff failed" in result.stderr

    def test_init_creates_contract(self, tmp_path):
        # init creates .diffcontract.yml in cwd
        result = subprocess.run(
            [sys.executable, "-m", "diff_contract.cli", "init"],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        assert result.returncode == 0
        assert (tmp_path / ".diffcontract.yml").exists()
        content = (tmp_path / ".diffcontract.yml").read_text()
        assert "rules" in content

    def test_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "diff_contract.cli", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "usage" in result.stdout.lower() or "help" in result.stdout.lower()

    def test_version(self):
        result = subprocess.run(
            [sys.executable, "-m", "diff_contract.cli", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "0.1.1" in result.stdout
