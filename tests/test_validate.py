"""Tests for the validate subcommand (no git dependency)."""

from __future__ import annotations

from diff_contract.cli import main


class TestValidateCommand:
    def test_validate_block_violation(self, tmp_path, capsys):
        contract = tmp_path / ".diffcontract.yml"
        contract.write_text("""version: 1
rules:
  - name: "Block core changes"
    deny:
      - "src/core/**"
    on_violation: block
""")
        result = main(["validate", "--contract", str(contract), "--files", "src/core/main.py"])
        assert result == 1

    def test_validate_clean(self, tmp_path, capsys):
        contract = tmp_path / ".diffcontract.yml"
        contract.write_text("""version: 1
rules:
  - name: "Block core changes"
    deny:
      - "src/core/**"
    on_violation: block
""")
        result = main(["validate", "--contract", str(contract), "--files", "src/app/main.py"])
        assert result == 0

    def test_validate_warn(self, tmp_path):
        contract = tmp_path / ".diffcontract.yml"
        contract.write_text("""version: 1
rules:
  - name: "Large diff warning"
    max_files: 1
    on_violation: warn
""")
        result = main(["validate", "--contract", str(contract), "--files", "a.py", "b.py"])
        assert result == 2

    def test_validate_json_output(self, tmp_path, capsys):
        contract = tmp_path / ".diffcontract.yml"
        contract.write_text("""version: 1
rules:
  - name: "Block core changes"
    deny:
      - "src/core/**"
    on_violation: block
""")
        result = main(
            [
                "validate",
                "--contract",
                str(contract),
                "--files",
                "src/core/main.py",
                "--output",
                "json",
            ]
        )
        captured = capsys.readouterr()
        import json

        data = json.loads(captured.out)
        assert data["clean"] is False
        assert data["block_count"] == 1
        assert result == 1

    def test_validate_from_stdin(self, tmp_path, monkeypatch):
        contract = tmp_path / ".diffcontract.yml"
        contract.write_text("""version: 1
rules:
  - name: "Block core changes"
    deny:
      - "src/core/**"
    on_violation: block
""")
        monkeypatch.setattr("sys.stdin", __import__("io").StringIO("src/core/main.py\n"))
        result = main(["validate", "--contract", str(contract), "--from-stdin"])
        assert result == 1

    def test_validate_no_files_error(self, tmp_path, capsys):
        contract = tmp_path / ".diffcontract.yml"
        contract.write_text("""version: 1
rules: []
""")
        result = main(["validate", "--contract", str(contract)])
        assert result == 1

    def test_validate_missing_contract(self, tmp_path):
        result = main(
            ["validate", "--contract", "/nonexistent/.diffcontract.yml", "--files", "a.py"]
        )
        assert result == 1
