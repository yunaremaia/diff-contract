"""The pre-commit hook is this tool's front door for pre-commit users, and it
was broken: ``entry: diff-contract check`` made pre-commit append staged
filenames as positional arguments, which argparse rejects ("unrecognized
arguments"), so every run with a matching file staged died with exit 2.

``check`` takes no positional arguments. The staged list has to go through
``--files``, which accepts nargs and absorbs them. These tests parse the real
hook manifest and assert the entry line is one the CLI actually accepts, so
the manifest cannot drift back into a form that exits 2.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS = yaml.safe_load((REPO_ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def hook() -> dict:
    return HOOKS[0]


def _entry_argv(hook: dict) -> list[str]:
    return hook["entry"].split()


def test_hook_id_is_stable(hook: dict) -> None:
    """Renaming the id silently breaks every existing user's .pre-commit-config."""
    assert hook["id"] == "diff-contract"


def test_entry_uses_the_files_flag_not_positional_arguments(hook: dict) -> None:
    """pre-commit appends filenames to the entry, so the entry must be a form
    that ends in an option taking a list -- never one that takes positionals."""
    argv = _entry_argv(hook)
    assert argv[:2] == ["diff-contract", "check"]
    assert "--files" in argv, (
        f"entry is {' '.join(argv)!r}: without --files, pre-commit's appended "
        "filenames become positional args and argparse exits 2 on every run"
    )
    assert argv[-1] == "--files", "--files must be last so appended filenames land in it"


def test_entry_actually_accepts_appended_filenames(hook: dict, tmp_path: Path) -> None:
    """Run the real CLI the way pre-commit invokes it: entry plus one staged
    path. This is the assertion that caught the original defect.

    A contract file must exist for the run to get past argument parsing, and the
    expected outcome is a clean pass -- otherwise a missing file would exit 1
    and the test would pass without ever proving the argv is accepted.
    """
    contract = tmp_path / "contract.yml"
    contract.write_text("rules:\n  - name: no-secrets\n    files: ['**/*']\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# fixture\n", encoding="utf-8")

    cmd = [*_entry_argv(hook), "README.md", "--contract", str(contract)]
    proc = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)
    assert proc.returncode != 2, (
        f"argparse rejected the invocation pre-commit would make:\n"
        f"{proc.stderr.strip()}\ncommand: {' '.join(cmd)}"
    )
    assert "unrecognized arguments" not in proc.stderr
    assert proc.returncode == 0, (
        f"a valid contract over a clean file must exit 0; got {proc.returncode}\n"
        f"stdout: {proc.stdout.strip()}\nstderr: {proc.stderr.strip()}"
    )


def test_hook_declares_its_language_and_dependencies(hook: dict) -> None:
    """`language: python` without additional_dependencies installs the hook
    from PyPI and silently runs whatever version the user last cached."""
    assert hook["language"] == "python"
    assert hook["additional_dependencies"], "hook must pin the diff-contract version it installs"
    assert any("diff-contract" in d for d in hook["additional_dependencies"])


def test_hook_matches_the_file_types_the_tool_can_rule_on(hook: dict) -> None:
    assert hook.get("files"), "hook without a files filter would run on every commit"


def test_hook_and_cli_share_the_same_subcommand() -> None:
    """Guards against the entry naming a subcommand the CLI does not have."""
    proc = subprocess.run(
        [sys.executable, "-m", "diff_contract.cli", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "check" in proc.stdout
