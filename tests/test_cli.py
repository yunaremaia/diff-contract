"""Tests for diff-contract CLI."""

import subprocess


class TestCli:
    def test_check_missing_file(self, tmp_path):
        result = subprocess.run(
            ["python", "-m", "diff_contract.cli", "check", "--contract", "/nonexistent/file.yaml"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_check_valid_contract(self, tmp_path):
        contract = tmp_path / "contract.yaml"
        contract.write_text("rules:\n  - name: no-todo\n    pattern: TODO\n    severity: warning\n")
        result = subprocess.run(
            ["python", "-m", "diff_contract.cli", "check", "--contract", str(contract)],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        assert result.returncode == 0

    def test_init_creates_contract(self, tmp_path):
        # init creates .diffcontract.yml in cwd
        result = subprocess.run(
            ["python", "-m", "diff_contract.cli", "init"],
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
            ["python", "-m", "diff_contract.cli", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "usage" in result.stdout.lower() or "help" in result.stdout.lower()

    def test_version(self):
        result = subprocess.run(
            ["python", "-m", "diff_contract.cli", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "0.1.1" in result.stdout
