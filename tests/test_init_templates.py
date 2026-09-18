"""Tests for diff-contract init --template."""

import subprocess
import sys


def test_init_template_help():
    """init --help shows --template option."""
    result = subprocess.run(
        [sys.executable, "-m", "diff_contract.cli", "init", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--template" in result.stdout
    assert "react" in result.stdout
    assert "django" in result.stdout
    assert "rust" in result.stdout
    assert "docs" in result.stdout


def test_init_default_python(tmp_path):
    """init without --template creates Python contract."""
    import os

    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "diff_contract.cli", "init"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        contract = tmp_path / ".diffcontract.yml"
        assert contract.exists()
        content = contract.read_text()
        assert "version: 1" in content
        assert "Protect CI/CD configs" in content
    finally:
        os.chdir(old_cwd)


def test_init_template_react(tmp_path):
    """init --template react creates React contract."""
    import os

    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "diff_contract.cli", "init", "--template", "react"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        contract = tmp_path / ".diffcontract.yml"
        assert contract.exists()
        content = contract.read_text()
        assert "React/Next.js" in content
        assert "app/**" in content
    finally:
        os.chdir(old_cwd)


def test_init_template_django(tmp_path):
    """init --template django creates Django contract."""
    import os

    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "diff_contract.cli", "init", "--template", "django"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        contract = tmp_path / ".diffcontract.yml"
        assert contract.exists()
        content = contract.read_text()
        assert "Django" in content
        assert "apps/**" in content
    finally:
        os.chdir(old_cwd)


def test_init_template_rust(tmp_path):
    """init --template rust creates Rust contract."""
    import os

    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "diff_contract.cli", "init", "--template", "rust"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        contract = tmp_path / ".diffcontract.yml"
        assert contract.exists()
        content = contract.read_text()
        assert "crates/**" in content
        assert "Cargo.toml" in content
    finally:
        os.chdir(old_cwd)


def test_init_template_docs(tmp_path):
    """init --template docs creates documentation-only contract."""
    import os

    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "diff_contract.cli", "init", "--template", "docs"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        contract = tmp_path / ".diffcontract.yml"
        assert contract.exists()
        content = contract.read_text()
        assert "docs/**" in content
        assert "*.md" in content
    finally:
        os.chdir(old_cwd)


def test_init_no_overwrite(tmp_path):
    """init does not overwrite existing contract."""
    import os

    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        contract = tmp_path / ".diffcontract.yml"
        contract.write_text("# existing contract\n")
        result = subprocess.run(
            [sys.executable, "-m", "diff_contract.cli", "init"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert contract.read_text() == "# existing contract\n"
    finally:
        os.chdir(old_cwd)
