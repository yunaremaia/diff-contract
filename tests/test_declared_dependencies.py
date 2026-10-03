"""Regression tests for the packaging contract.

Two defects are guarded here, both of which survive CI unnoticed because CI runs
``pip install -e .`` and resolves imports from the source tree:

1. An import that is not declared in ``[project] dependencies`` passes every test
   in an editable install and then crashes a real ``pip install`` from a wheel.
2. A literal ``__version__ = "x.y.z"`` in ``__init__.py`` makes the version
   reported by ``--version`` permanently wrong once a release bumps
   ``pyproject.toml`` without editing the literal.

The walk below is stdlib-only on purpose: it must run in the same environment as
the package's own tests, with no extra dependency installed.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    tomllib = None  # type: ignore[assignment]

import diff_contract

DIST_NAME = "diff-contract"
MODULE_NAME = "diff_contract"

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = REPO_ROOT / "src" / MODULE_NAME

# Distribution names whose import name differs from the distribution name.
IMPORT_ALIASES = {
    "pyyaml": "yaml",
}

# Test-only and build-time tooling: never a runtime dependency, so an import of
# one of these must not be reported as an undeclared dependency.
DEV_ONLY = {
    "_pytest",
    "build",
    "coverage",
    "freezegun",
    "hypothesis",
    "mypy",
    "nox",
    "pytest",
    "pytest_cov",
    "pytest_timeout",
    "pytest_xdist",
    "ruff",
    "setuptools",
    "tox",
    "wheel",
    "xdist",
}


def normalize(name: str) -> str:
    return name.lower().replace("_", "-").replace(".", "-")


def canonical(name: str) -> str:
    """tomllib and tomli are one dependency, spelled two ways."""
    return "tomllib" if name in {"tomllib", "tomli"} else name


def iter_source_files() -> list[Path]:
    return sorted(p for p in PACKAGE_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


def top_level_imports() -> set[str]:
    """Every top-level module name imported anywhere in the package source."""
    found: set[str] = set()
    for path in iter_source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                # node.level > 0 is a relative import: first-party, not a dependency.
                found.add(node.module.split(".")[0])
    return found


def third_party_imports() -> set[str]:
    stdlib = set(sys.stdlib_module_names) | {"tomllib", "tomli_w"}
    first_party = {MODULE_NAME}
    subpackages = {
        p.name for p in PACKAGE_ROOT.iterdir()
        if p.is_dir() and (p / "__init__.py").exists()
    } if PACKAGE_ROOT.is_dir() else set()
    first_party = first_party | subpackages
    # canonical() is applied on BOTH sides of the cross-check: a try/except
    # tomllib/tomli fallback puts two spellings of one dependency in the source,
    # and only canonicalising the declared list would report the other as
    # undeclared.
    return {
        canonical(m) for m in top_level_imports()
        if m not in stdlib and m not in first_party and m not in DEV_ONLY
    }


def read_pyproject_dependencies() -> list[str]:
    """[project] dependencies, straight from pyproject.toml.

    pyproject is the single source of truth on purpose: a hardcoded copy would
    make these checks compare the source tree against itself and could never
    report a dependency that is missing from pyproject.
    """
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if tomllib is not None:
        return list(tomllib.loads(text)["project"]["dependencies"])
    # Python 3.10 without tomli: parse just the dependencies array as text.
    body = text.split("dependencies = [", 1)[1].split("]", 1)[0]
    return [
        line.strip().strip('",')
        for line in body.splitlines()
        if line.strip().startswith('"')
    ]


def declared_import_names() -> set[str]:
    """Import names implied by [project] dependencies in pyproject.toml."""
    names = set()
    for spec in read_pyproject_dependencies():
        dist = spec.split(";", 1)[0]
        for sep in ("<", ">", "=", "!", "~", "[", " ", "@"):
            dist = dist.split(sep, 1)[0]
        dist = normalize(dist.strip())
        if not dist:
            continue
        names.add(canonical(IMPORT_ALIASES.get(dist, dist)))
    return names


def test_every_import_is_declared_in_pyproject() -> None:
    """An undeclared import crashes a real wheel install with ModuleNotFoundError."""
    undeclared = sorted(third_party_imports() - declared_import_names())
    assert not undeclared, (
        "these modules are imported by the package but are not declared in "
        f"[project] dependencies: {undeclared}. A `pip install` of the built "
        "wheel will fail with ModuleNotFoundError; `pip install -e .` in CI "
        "hides this because it resolves imports from the source tree."
    )


def test_every_declared_dependency_is_imported() -> None:
    """A declared dependency nothing imports is dead weight that misleads readers."""
    unused = sorted(declared_import_names() - third_party_imports())
    assert not unused, (
        "these are declared in [project] dependencies but never imported by "
        f"the package source: {unused}. Remove them or import them."
    )


def _package_not_found_fallback_lines(tree: ast.AST) -> set[int]:
    """Line numbers of __version__ literals guarded by except PackageNotFoundError.

    A bare ``__version__ = "0.0.0.dev0"`` is only legitimate inside that
    handler, where it marks "running from a source checkout, not an install".
    The same literal at module level is the stale-version bug.
    """
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        handles_not_found = any(
            (isinstance(h.type, ast.Name) and h.type.id == "PackageNotFoundError")
            or (isinstance(h.type, ast.Tuple)
                and any(isinstance(e, ast.Name) and e.id == "PackageNotFoundError"
                        for e in h.type.elts))
            for h in node.handlers
        )
        if not handles_not_found:
            continue
        for handler in node.handlers:
            for stmt in handler.body:
                for inner in ast.walk(stmt):
                    if isinstance(inner, ast.Assign):
                        for target in inner.targets:
                            if isinstance(target, ast.Name) and target.id == "__version__":
                                guarded.add(inner.lineno)
    return guarded


def test_version_is_not_a_literal_assignment() -> None:
    """A literal __version__ goes stale the moment a release bumps pyproject.toml."""
    init = PACKAGE_ROOT / "__init__.py"
    tree = ast.parse(init.read_text(encoding="utf-8"), filename=str(init))
    guarded = _package_not_found_fallback_lines(tree)

    literals = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ]

    stale = [n for n in literals if n.lineno not in guarded]
    assert not stale, (
        f"{init.name}:{stale[0].lineno} assigns __version__ a string literal "
        "outside an `except PackageNotFoundError` handler. Use "
        "importlib.metadata.version(DIST_NAME) so the reported version always "
        "matches the installed metadata."
    )


def test_version_is_read_from_importlib_metadata() -> None:
    """The value must come from the distribution, keyed by DIST name not module."""
    init = PACKAGE_ROOT / "__init__.py"
    tree = ast.parse(init.read_text(encoding="utf-8"), filename=str(init))
    calls = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and "metadata_version" in node.func.id
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    assert calls == {DIST_NAME}, (
        f"{init.name} must resolve __version__ through "
        f'importlib.metadata.version("{DIST_NAME}"), got {sorted(calls) or "nothing"}. '
        f"{DIST_NAME} is the distribution name; {MODULE_NAME} is the import "
        "name, and they are not interchangeable."
    )


def test_version_comes_from_installed_metadata() -> None:
    """importlib.metadata must resolve the real distribution name, not the module."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        expected = version(DIST_NAME)
    except PackageNotFoundError:
        pytest.skip("not installed as a distribution (bare source checkout)")
        return
    assert diff_contract.__version__ == expected


def test_cli_version_agrees_with_the_module() -> None:
    """`--version` is the only thing most users ever see; it must not drift."""
    # The console script, not `python -m`, because a project's entry point may
    # live anywhere and some CLIs (argparse-based) have no `__main__` at all.
    # Resolved through shutil so a checkout without the package installed skips
    # instead of failing on a missing binary.
    import shutil

    binary = shutil.which("diff-contract")
    if binary is None:
        pytest.skip("diff-contract is not installed in this environment")
    result = subprocess.run(
        [binary, "--version"], capture_output=True, text=True, cwd=REPO_ROOT,
        check=False,
    )
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0 and "No module named" in output:
        pytest.skip("diff-contract is not runnable here")
    assert diff_contract.__version__ in output, (
        f"CLI reported {output!r} but the module reports "
        f"{diff_contract.__version__!r}. Both must come from the installed metadata."
    )
