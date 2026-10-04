"""In-process behavioural tests for the ``check`` and ``init`` CLI code paths.

Every test here used to be invisible to coverage. The existing ``check`` tests
shelled out with ``subprocess.run([sys.executable, "-m", "diff_contract.cli",
...])``, so the code they exercised ran in a *different interpreter* that
coverage never measured — ``_cmd_check`` and ``_cmd_init`` sat at zero lines
covered while looking "tested" in review.

Calling ``main([...])`` in-process fixes the measurement gap, and these are
written as behavioural assertions rather than smoke tests: each one pins an
exit code, a stderr stream, or an exact output line, so a mutation that swaps
a return code, inverts a condition or reorders a precedence rule turns the
suite red instead of silently passing.
"""

from __future__ import annotations

import io
import json
import runpy
import subprocess
import sys
import warnings
from pathlib import Path

import pytest

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from diff_contract import __version__
from diff_contract.cli import _TEMPLATES, main

REPO_ROOT = Path(__file__).resolve().parents[1]


def write_contract(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


BLOCK_CONTRACT = """version: 1
rules:
  - name: "Deny core"
    deny: ["src/core/**"]
    on_violation: block
"""

WARN_CONTRACT = """version: 1
rules:
  - name: "Large diff warning"
    max_files: 1
    on_violation: warn
"""

# Two violations with different severities in one run: the check command must
# report both and still exit 1, because a block outranks a warn.
MIXED_CONTRACT = """version: 1
rules:
  - name: "Deny core"
    deny: ["src/core/**"]
    on_violation: block
  - name: "Large diff warning"
    max_files: 1
    on_violation: warn
"""


class Recorder:
    """Collect stdout/stderr separately so a test can assert *which stream*."""

    def __init__(self) -> None:
        self.out = io.StringIO()
        self.err = io.StringIO()

    def run(self, argv: list[str]) -> int:
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = self.out, self.err
        try:
            return main(argv)
        finally:
            sys.stdout, sys.stderr = old_out, old_err

    @property
    def stdout(self) -> str:
        return self.out.getvalue()

    @property
    def stderr(self) -> str:
        return self.err.getvalue()


class TestCheckMissingContract:
    def test_missing_contract_exits_1_and_names_the_path_on_stderr(self, tmp_path):
        """A typo in --contract must fail loudly, not silently pass as clean."""
        missing = tmp_path / "nope.yml"
        rec = Recorder()

        rc = rec.run(["check", "--contract", str(missing), "--files", "a.py"])

        assert rc == 1
        assert f"ERROR: Contract not found: {missing}" in rec.stderr
        # Nothing may reach stdout: a clean-run banner here would read as success.
        assert "clean" not in rec.stdout

    def test_missing_contract_never_falls_through_to_git(self, tmp_path, monkeypatch):
        """The contract is loaded before git runs, so a missing file costs no git call."""
        import diff_contract.cli as cli_mod

        def explode(*a, **k):  # pragma: no cover - must never execute
            raise AssertionError("git diff ran despite a missing contract")

        monkeypatch.setattr(cli_mod, "DiffCalculator", explode)
        rec = Recorder()

        rc = rec.run(["check", "--contract", str(tmp_path / "absent.yml"), "--files", "a.py"])

        assert rc == 1
        assert "Contract not found" in rec.stderr


class TestMalformedContract:
    """A contract the parser rejects must be a one-line error, never a traceback.

    Each body below is a reproducer from #95. Before load_contract() was
    wrapped, every one of them escaped as a raw Python traceback: nine library
    frames for what is a one-character typo. The contract file is the user's
    input, so a parse failure is an expected outcome of the command, not a bug
    in it — and the exit code must stay 1 so scripts see a contract failure
    rather than a crash.
    """

    MALFORMED = {
        "bad_on_violation": "version: 1\nrules:\n  - name: X\n    on_violation: critcal\n",
        "list_document_root": "- a\n- b\n",
        "bare_string_rules": 'version: 1\nrules: "src/**"\n',
        "string_allow_field": 'version: 1\nrules:\n  - name: X\n    allow: "src/**"\n',
    }

    @pytest.mark.parametrize("case", sorted(MALFORMED))
    def test_check_reports_a_malformed_contract_without_a_traceback(self, tmp_path, case):
        contract = write_contract(tmp_path / "bad.yml", self.MALFORMED[case])
        rec = Recorder()

        rc = rec.run(["check", "--contract", str(contract), "--files", "a.py"])

        assert rc == 1
        err = rec.stderr
        assert f"ERROR: Invalid contract {contract}:" in err
        # The whole point of the fix: no library frames leak to the user.
        assert "Traceback" not in err
        assert "diff_contract" not in err
        # A parse failure must not read as a clean run on stdout.
        assert "clean" not in rec.stdout

    @pytest.mark.parametrize("case", sorted(MALFORMED))
    def test_validate_reports_a_malformed_contract_without_a_traceback(self, tmp_path, case):
        """_cmd_validate is a separate call site and needs the same guarantee."""
        contract = write_contract(tmp_path / "bad.yml", self.MALFORMED[case])
        rec = Recorder()

        rc = rec.run(["validate", "--contract", str(contract), "--files", "a.py"])

        assert rc == 1
        err = rec.stderr
        assert f"ERROR: Invalid contract {contract}:" in err
        assert "Traceback" not in err

    def test_the_parser_message_is_preserved_in_the_error_line(self, tmp_path):
        """Wrapping must not swallow the detail that tells the user what to fix."""
        contract = write_contract(
            tmp_path / "bad.yml", self.MALFORMED["bad_on_violation"]
        )
        rec = Recorder()

        rec.run(["check", "--contract", str(contract), "--files", "a.py"])

        # The rule index and the valid values both survive into the one line.
        assert "critcal" in rec.stderr
        assert "rule 0" in rec.stderr
        assert "block" in rec.stderr


class TestCheckFileSelection:
    def test_files_flag_bypasses_git_entirely(self, non_git_dir, tmp_path):
        """--files must work where git cannot run at all (CI without a checkout)."""
        contract = write_contract(non_git_dir / "c.yml", "version: 1\nrules: []\n")
        rec = Recorder()

        rc = rec.run(["check", "--contract", str(contract), "--files", "a.py"])

        assert rc == 0
        assert "✓ Diff is clean" in rec.stdout
        assert rec.stderr == ""

    def test_files_flag_passes_every_file_to_the_engine(self, tmp_path):
        """Every --files entry must reach the engine, not just the first one."""
        contract = write_contract(tmp_path / "c.yml", MIXED_CONTRACT)
        seen: list = []
        import diff_contract.cli as cli_mod

        original = cli_mod.RulesEngine

        class Spy(original):  # type: ignore[misc, valid-type]
            def check(self, changed_files):
                seen.extend(changed_files)
                return super().check(changed_files)

        cli_mod.RulesEngine = Spy
        try:
            rc = Recorder().run(
                ["check", "--contract", str(contract), "--files", "src/core/a.py", "b.py", "c.py"]
            )
        finally:
            cli_mod.RulesEngine = original

        assert rc == 1  # the deny rule matched src/core/a.py
        assert seen == ["src/core/a.py", "b.py", "c.py"]

    def test_without_files_flag_it_uses_git_with_the_default_base_branch(
        self, tmp_path, monkeypatch
    ):
        """No --files means "diff against main"; the default base is what CI relies on."""
        import diff_contract.cli as cli_mod

        contract = write_contract(tmp_path / "c.yml", BLOCK_CONTRACT)
        captured: dict = {}

        class FakeCalc:
            def __init__(self, base_branch="main", cwd=None):
                captured["base_branch"] = base_branch

            def get_changed_files(self):
                return [{"path": "src/core/a.py", "lines": 3}]

        monkeypatch.setattr(cli_mod, "DiffCalculator", FakeCalc)

        rc = Recorder().run(["check", "--contract", str(contract)])

        assert captured["base_branch"] == "main"
        assert rc == 1  # the git-supplied path tripped the deny rule

    def test_base_flag_overrides_the_default_base_branch(self, tmp_path, monkeypatch):
        """--base must reach DiffCalculator; defaulting it to main breaks release branches."""
        import diff_contract.cli as cli_mod

        contract = write_contract(tmp_path / "c.yml", "version: 1\nrules: []\n")
        captured: dict = {}

        class FakeCalc:
            def __init__(self, base_branch="main", cwd=None):
                captured["base_branch"] = base_branch

            def get_changed_files(self):
                return []

        monkeypatch.setattr(cli_mod, "DiffCalculator", FakeCalc)

        rc = Recorder().run(["check", "--contract", str(contract), "--base", "develop"])

        assert captured["base_branch"] == "develop"
        assert rc == 0


class TestCheckGitFailure:
    def test_git_diff_error_exits_1_and_prints_the_reason_to_stderr(self, non_git_dir):
        """A git failure must surface its cause, not a bare non-zero code."""
        contract = write_contract(non_git_dir / "c.yml", "version: 1\nrules: []\n")
        rec = Recorder()

        with pytest.MonkeyPatch.context() as mp:
            mp.chdir(non_git_dir)
            rc = rec.run(["check", "--contract", str(contract)])

        assert rc == 1
        assert rec.stderr.startswith("ERROR: ")
        assert "git diff failed" in rec.stderr
        # A failure must not be dressed up as a clean diff on stdout.
        assert "Diff is clean" not in rec.stdout

    def test_git_diff_error_keeps_the_engine_from_running(self, non_git_dir, monkeypatch):
        """Returning early on GitDiffError is the point: no rules run on no data."""
        import diff_contract.cli as cli_mod

        contract = write_contract(non_git_dir / "c.yml", "version: 1\nrules: []\n")

        class Boom:  # pragma: no cover - must never execute
            def __init__(self, *a, **k):
                raise AssertionError("RulesEngine ran after a git failure")

        monkeypatch.setattr(cli_mod, "RulesEngine", Boom)
        rec = Recorder()
        with pytest.MonkeyPatch.context() as mp:
            mp.chdir(non_git_dir)
            rc = rec.run(["check", "--contract", str(contract)])

        assert rc == 1
        assert "git diff failed" in rec.stderr


class TestCheckExitCodes:
    """0 clean / 1 block / 2 warn. A CI gate is only as good as these numbers."""

    def test_clean_diff_exits_0(self, tmp_path):
        contract = write_contract(tmp_path / "c.yml", "version: 1\nrules: []\n")
        rec = Recorder()

        rc = rec.run(["check", "--contract", str(contract), "--files", "README.md"])

        assert rc == 0
        assert "✓ Diff is clean" in rec.stdout

    def test_block_violation_exits_1(self, tmp_path):
        contract = write_contract(tmp_path / "c.yml", BLOCK_CONTRACT)
        rec = Recorder()

        rc = rec.run(["check", "--contract", str(contract), "--files", "src/core/main.py"])

        assert rc == 1
        assert "is denied by rule" in rec.stdout

    def test_warn_violation_exits_2(self, tmp_path):
        contract = write_contract(tmp_path / "c.yml", WARN_CONTRACT)
        rec = Recorder()

        rc = rec.run(["check", "--contract", str(contract), "--files", "a.py", "b.py"])

        assert rc == 2, "a warn must be distinguishable from a block by exit code"

    def test_block_outranks_warn_in_the_exit_code(self, tmp_path):
        """A run with both severities must exit 1, not 2 — block is the CI gate."""
        contract = write_contract(tmp_path / "c.yml", MIXED_CONTRACT)
        rec = Recorder()

        rc = rec.run(
            ["check", "--contract", str(contract), "--files", "src/core/main.py", "b.py"]
        )

        assert rc == 1
        assert "2 violation(s):" in rec.stdout


class TestCheckTextOutput:
    def test_clean_run_prints_the_clean_banner(self, tmp_path):
        contract = write_contract(tmp_path / "c.yml", "version: 1\nrules: []\n")
        rec = Recorder()

        rec.run(["check", "--contract", str(contract), "--files", "a.py"])

        assert rec.stdout == "✓ Diff is clean — no contract violations\n"

    def test_violation_header_reports_the_exact_count(self, tmp_path):
        """The header count is the number of violations, not a hardcoded total.

        Three deny rules fire on ``src/core/a.py`` and one more on ``b.py``, so
        a wrong count — a literal, or an off-by-one in the aggregation — shows
        up immediately.
        """
        contract = write_contract(
            tmp_path / "c.yml",
            """version: 1
rules:
  - name: "Deny py"
    deny: ["*.py"]
    on_violation: block
  - name: "Deny src"
    deny: ["src/**"]
    on_violation: block
  - name: "Deny core"
    deny: ["src/core/**"]
    on_violation: block
""",
        )
        rec = Recorder()

        rec.run(["check", "--contract", str(contract), "--files", "src/core/a.py", "b.py"])

        assert "✗ 4 violation(s):" in rec.stdout
        assert len([ln for ln in rec.stdout.splitlines() if "🔴" in ln]) == 4

    def test_block_uses_a_red_icon_and_uppercase_severity(self, tmp_path):
        contract = write_contract(tmp_path / "c.yml", BLOCK_CONTRACT)
        rec = Recorder()

        rec.run(["check", "--contract", str(contract), "--files", "src/core/main.py"])

        assert "  🔴 [BLOCK] File 'src/core/main.py' is denied by rule 'Deny core'" in rec.stdout

    def test_warn_uses_a_yellow_icon_and_uppercase_severity(self, tmp_path):
        contract = write_contract(tmp_path / "c.yml", WARN_CONTRACT)
        rec = Recorder()

        rec.run(["check", "--contract", str(contract), "--files", "a.py", "b.py"])

        assert "  🟡 [WARN] Too many files changed (2 > 1)" in rec.stdout


class TestCheckJsonOutput:
    def test_clean_json_reports_zeroed_counters(self, tmp_path):
        contract = write_contract(tmp_path / "c.yml", "version: 1\nrules: []\n")
        rec = Recorder()

        rc = rec.run(["check", "--contract", str(contract), "--files", "a.py", "--output", "json"])

        payload = json.loads(rec.stdout)
        assert rc == 0
        assert payload == {"clean": True, "block_count": 0, "warn_count": 0, "violations": []}

    def test_block_json_reports_the_count_and_the_offending_file(self, tmp_path):
        contract = write_contract(tmp_path / "c.yml", BLOCK_CONTRACT)
        rec = Recorder()

        rc = rec.run(
            [
                "check",
                "--contract",
                str(contract),
                "--files",
                "src/core/main.py",
                "--output",
                "json",
            ]
        )

        payload = json.loads(rec.stdout)
        assert rc == 1
        assert payload["clean"] is False
        assert payload["block_count"] == 1
        assert payload["warn_count"] == 0
        assert payload["violations"] == [
            {
                "file": "src/core/main.py",
                "severity": "block",
                "rule": "Deny core",
                "message": "File 'src/core/main.py' is denied by rule 'Deny core'",
            }
        ]

    def test_warn_json_counts_a_warn_and_not_a_block(self, tmp_path):
        """A swapped severity enum here would report block_count=1 for a warn."""
        contract = write_contract(tmp_path / "c.yml", WARN_CONTRACT)
        rec = Recorder()

        rc = rec.run(
            [
                "check",
                "--contract",
                str(contract),
                "--files",
                "a.py",
                "b.py",
                "--output",
                "json",
            ]
        )

        payload = json.loads(rec.stdout)
        assert rc == 2
        assert payload["clean"] is False
        assert payload["block_count"] == 0
        assert payload["warn_count"] == 1
        assert payload["violations"][0]["severity"] == "warn"
        assert payload["violations"][0]["file"] == "<aggregate>"

    def test_mixed_json_separates_the_two_counters(self, tmp_path):
        contract = write_contract(tmp_path / "c.yml", MIXED_CONTRACT)
        rec = Recorder()

        rc = rec.run(
            [
                "check",
                "--contract",
                str(contract),
                "--files",
                "src/core/a.py",
                "b.py",
                "--output",
                "json",
            ]
        )

        payload = json.loads(rec.stdout)
        assert rc == 1
        assert payload["block_count"] == 1
        assert payload["warn_count"] == 1
        assert sorted(v["severity"] for v in payload["violations"]) == ["block", "warn"]


class TestCheckSarifOutput:
    def test_sarif_flag_emits_a_2_1_0_document(self, tmp_path):
        contract = write_contract(tmp_path / "c.yml", BLOCK_CONTRACT)
        rec = Recorder()

        rec.run(
            ["check", "--contract", str(contract), "--files", "src/core/main.py", "--sarif"]
        )

        doc = json.loads(rec.stdout)
        assert doc["version"] == "2.1.0"
        assert doc["runs"][0]["tool"]["driver"]["name"] == "diff-contract"

    def test_sarif_preserves_the_block_exit_code(self, tmp_path):
        """--sarif changes the report format, not the gate: a block still exits 1."""
        contract = write_contract(tmp_path / "c.yml", BLOCK_CONTRACT)
        rec = Recorder()

        rc = rec.run(
            ["check", "--contract", str(contract), "--files", "src/core/main.py", "--sarif"]
        )

        assert rc == 1

    def test_sarif_preserves_the_clean_exit_code_and_empty_results(self, tmp_path):
        contract = write_contract(tmp_path / "c.yml", "version: 1\nrules: []\n")
        rec = Recorder()

        rc = rec.run(["check", "--contract", str(contract), "--files", "a.py", "--sarif"])

        assert rc == 0
        assert json.loads(rec.stdout)["runs"][0]["results"] == []

    def test_sarif_takes_precedence_over_json_output(self, tmp_path):
        """With both flags, SARIF wins — the Code Scanning upload must still parse."""
        contract = write_contract(tmp_path / "c.yml", BLOCK_CONTRACT)
        rec = Recorder()

        rc = rec.run(
            [
                "check",
                "--contract",
                str(contract),
                "--files",
                "src/core/main.py",
                "--output",
                "json",
                "--sarif",
            ]
        )

        assert rc == 1
        assert json.loads(rec.stdout)["version"] == "2.1.0"

    def test_sarif_error_level_for_a_block(self, tmp_path):
        contract = write_contract(tmp_path / "c.yml", BLOCK_CONTRACT)
        rec = Recorder()

        rec.run(
            ["check", "--contract", str(contract), "--files", "src/core/main.py", "--sarif"]
        )

        results = json.loads(rec.stdout)["runs"][0]["results"]
        assert [r["level"] for r in results] == ["error"]
        assert results[0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == (
            "src/core/main.py"
        )


class TestValidateSarifPath:
    def test_validate_sarif_emits_a_document_and_keeps_the_block_exit_code(self, tmp_path):
        contract = write_contract(tmp_path / "c.yml", BLOCK_CONTRACT)
        rec = Recorder()

        rc = rec.run(
            ["validate", "--contract", str(contract), "--files", "src/core/a.py", "--sarif"]
        )

        assert rc == 1
        doc = json.loads(rec.stdout)
        assert doc["version"] == "2.1.0"
        assert [r["level"] for r in doc["runs"][0]["results"]] == ["error"]

    def test_validate_sarif_on_a_clean_run_has_no_results(self, tmp_path):
        contract = write_contract(tmp_path / "c.yml", "version: 1\nrules: []\n")
        rec = Recorder()

        rc = rec.run(["validate", "--contract", str(contract), "--files", "a.py", "--sarif"])

        assert rc == 0
        assert json.loads(rec.stdout)["runs"][0]["results"] == []


class TestValidateInputSelection:
    def test_from_stdin_strips_blank_lines(self, tmp_path, monkeypatch):
        """Blank lines from `git diff --name-only` must not become empty paths."""
        contract = write_contract(tmp_path / "c.yml", "version: 1\nrules: []\n")
        monkeypatch.setattr(
            sys, "stdin", io.StringIO("src/core/a.py\n\n   \nsrc/core/b.py\n\n")
        )
        seen: list = []
        import diff_contract.cli as cli_mod

        original = cli_mod.RulesEngine

        class Spy(original):  # type: ignore[misc, valid-type]
            def check(self, changed_files):
                seen.extend(changed_files)
                return super().check(changed_files)

        monkeypatch.setattr(cli_mod, "RulesEngine", Spy)

        rc = Recorder().run(["validate", "--contract", str(contract), "--from-stdin"])

        assert rc == 0
        assert seen == ["src/core/a.py", "src/core/b.py"]

    def test_from_stdin_wins_when_both_inputs_are_given(self, tmp_path, monkeypatch):
        """--from-stdin is checked first; --files must not silently override it."""
        contract = write_contract(tmp_path / "c.yml", BLOCK_CONTRACT)
        monkeypatch.setattr(sys, "stdin", io.StringIO("docs/readme.md\n"))
        rec = Recorder()

        rc = rec.run(
            [
                "validate",
                "--contract",
                str(contract),
                "--from-stdin",
                "--files",
                "src/core/blocked.py",
            ]
        )

        assert rc == 0, "the stdin file is clean; the --files entry must not have been used"
        assert "Diff is clean" in rec.stdout

    def test_no_input_reports_the_missing_input_on_stderr(self, tmp_path):
        contract = write_contract(tmp_path / "c.yml", "version: 1\nrules: []\n")
        rec = Recorder()

        rc = rec.run(["validate", "--contract", str(contract)])

        assert rc == 1
        assert "ERROR: Provide --files or --from-stdin" in rec.stderr
        assert "Diff is clean" not in rec.stdout


class TestInitCommand:
    def test_init_writes_the_python_template_into_the_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        rec = Recorder()

        rc = rec.run(["init"])

        written = tmp_path / ".diffcontract.yml"
        assert rc == 0
        assert written.read_text(encoding="utf-8") == _TEMPLATES["python"]
        assert "✓ Created .diffcontract.yml (template: python)" in rec.stdout

    @pytest.mark.parametrize("template", ["python", "react", "django", "rust", "docs"])
    def test_init_writes_the_requested_template(self, template, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        rec = Recorder()

        rc = rec.run(["init", "--template", template])

        assert rc == 0
        assert (tmp_path / ".diffcontract.yml").read_text(encoding="utf-8") == (
            _TEMPLATES[template]
        )
        assert f"(template: {template})" in rec.stdout

    def test_init_refuses_to_overwrite_and_keeps_the_original_bytes(
        self, tmp_path, monkeypatch
    ):
        """Clobbering a hand-tuned contract is unrecoverable data loss."""
        monkeypatch.chdir(tmp_path)
        target = tmp_path / ".diffcontract.yml"
        target.write_text("# my carefully tuned contract\n", encoding="utf-8")
        rec = Recorder()

        rc = rec.run(["init"])

        assert rc == 1
        assert target.read_text(encoding="utf-8") == "# my carefully tuned contract\n"
        assert "WARNING: .diffcontract.yml already exists — not overwriting" in rec.stderr
        assert "Created" not in rec.stdout

    def test_init_unknown_template_falls_back_to_python_content(self, tmp_path, monkeypatch):
        """_cmd_init is importable, so its .get() default has to mean something."""
        from diff_contract.cli import _cmd_init

        monkeypatch.chdir(tmp_path)

        rc = _cmd_init("klingon")

        assert rc == 0
        assert (tmp_path / ".diffcontract.yml").read_text(encoding="utf-8") == (
            _TEMPLATES["python"]
        )

    def test_init_rejects_a_template_outside_the_choices(self, tmp_path, monkeypatch):
        """argparse must refuse an unknown template rather than write a wrong one."""
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit) as excinfo:
            Recorder().run(["init", "--template", "klingon"])

        assert excinfo.value.code == 2
        assert not (tmp_path / ".diffcontract.yml").exists()

    @pytest.mark.parametrize("command", ["check", "validate"])
    def test_check_and_validate_reject_an_unknown_output_choice(self, command, capsys):
        """A typo'd --output must be a usage error, not a silent fallback to text.

        This test exists because mutation testing asked for it: dropping
        `choices=` from `check`'s `--output` left every other test in the suite
        green while the CLI quietly accepted `--output bogus` and printed the
        text report anyway — so a caller asking for JSON to pipe into a parser
        got prose and exit 0.
        """
        with pytest.raises(SystemExit) as excinfo:
            main([command, "--output", "bogus", "--files", "a.py"])

        assert excinfo.value.code == 2
        err = capsys.readouterr().err
        assert "invalid choice" in err
        assert "bogus" in err

    def test_contract_path_is_not_choice_constrained(self, capsys):
        """The positive control for the test above.

        `--contract` is a free-form path, so a rejection here would mean the
        previous test passes for the wrong reason (argparse refusing everything)
        rather than because `choices` is enforced where it belongs.
        """
        rec = Recorder()

        rc = rec.run(["check", "--contract", "bogus", "--files", "a.py"])

        assert rc == 1  # a missing file, not a usage error
        assert "ERROR: Contract not found: bogus" in rec.stderr
        assert "invalid choice" not in rec.stderr


class TestDispatch:
    def test_init_subcommand_is_routed_to_init(self, tmp_path, monkeypatch):
        """The dispatch chain must reach _cmd_init, not fall through to help."""
        monkeypatch.chdir(tmp_path)
        rec = Recorder()

        rc = rec.run(["init"])

        assert rc == 0
        assert (tmp_path / ".diffcontract.yml").exists()
        assert "usage:" not in rec.stdout

    def test_no_subcommand_exits_2_with_usage(self, capsys):
        """`required=True` makes an empty invocation a usage error, not a help dump."""
        with pytest.raises(SystemExit) as excinfo:
            main([])

        assert excinfo.value.code == 2
        assert "the following arguments are required: command" in capsys.readouterr().err

    def test_unknown_subcommand_exits_2_listing_the_valid_ones(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            main(["lint"])

        assert excinfo.value.code == 2
        err = capsys.readouterr().err
        assert "invalid choice" in err
        for command in ("check", "validate", "init"):
            assert command in err

    def test_help_uses_the_installed_program_name(self, capsys):
        """`prog` is what users type; a bare 'usage: cli.py' misleads everyone."""
        with pytest.raises(SystemExit) as excinfo:
            main(["--help"])

        assert excinfo.value.code == 0
        assert capsys.readouterr().out.startswith("usage: diff-contract ")

    def test_module_entry_point_exits_with_the_return_code(self, tmp_path, monkeypatch):
        """`python -m diff_contract.cli` must forward main()'s return as the process code."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            sys,
            "argv",
            ["diff-contract", "validate", "--contract", "/nonexistent/c.yml", "--files", "a.py"],
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            with pytest.raises(SystemExit) as excinfo:
                runpy.run_module("diff_contract.cli", run_name="__main__", alter_sys=True)

        assert excinfo.value.code == 1


class TestVersionFlag:
    def test_version_flag_matches_the_package_metadata(self, capsys):
        """`--version` is how a user reports a bug; a stale number misfiles it.

        The version used to be a hand-copied literal that drifted from
        pyproject.toml, so the released 0.1.2 wheel answered `0.1.1`.
        """
        with pytest.raises(SystemExit) as excinfo:
            main(["--version"])

        assert excinfo.value.code == 0
        assert capsys.readouterr().out.strip() == f"diff-contract {__version__}"

    def test_declared_version_matches_the_published_version(self):
        """One source of truth: __init__ must agree with the packaging metadata."""
        project = tomllib.loads(
            (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]

        assert __version__ == project["version"], (
            f"diff_contract.__version__ is {__version__} but pyproject.toml declares "
            f"{project['version']}; --version will report the wrong release"
        )

    def test_console_script_version_matches_module_version(self):
        """The installed `diff-contract --version` must equal `python -m`'s answer."""
        module = subprocess.run(
            [sys.executable, "-m", "diff_contract.cli", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert module.stdout.strip() == f"diff-contract {__version__}"
        assert "0.1.1" not in module.stdout or __version__ == "0.1.1"
