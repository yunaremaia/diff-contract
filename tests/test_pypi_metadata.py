"""The published metadata is the project's only shop window — keep it complete.

A package can be installable and still be invisible. PyPI indexes
``keywords`` for search, renders ``project.urls`` as the only navigational
links on the landing page, and shows a README badge to tell a visitor which
release is current. Each of those fields was empty or missing here at least
once, so an omission is now a test failure instead of something nobody
notices until the next release is cut.
"""

from __future__ import annotations

from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")


def test_keywords_are_indexed():
    """An empty keyword list makes the package unfindable by topic."""
    keywords = PROJECT.get("keywords") or []
    assert keywords, (
        "project.keywords is empty; PyPI indexes these for search, so an empty "
        "list hides the package from every topic query"
    )
    assert all(k.strip() for k in keywords), f"blank keyword in {keywords!r}"


def test_authors_are_declared():
    authors = PROJECT.get("authors") or []
    assert authors, "project.authors is empty: the landing page shows no maintainer"
    for author in authors:
        assert author.get("name"), f"author without a name: {author!r}"


@pytest.mark.parametrize("label", ["Homepage", "Issues", "Funding", "Changelog"])
def test_project_url_is_present(label: str) -> None:
    urls = PROJECT.get("urls") or {}
    assert label in urls, (
        f"project.urls is missing {label!r}; the landing page offers only "
        f"{sorted(urls) or 'no links at all'}"
    )
    assert urls[label].startswith("https://"), f"{label} must be an https URL, got {urls[label]!r}"


def test_readme_shows_the_pypi_version_badge() -> None:
    """The version badge is the first thing a visitor reads before installing."""
    dist = PROJECT["name"]
    assert f"img.shields.io/pypi/v/{dist}" in README, (
        f"README has no PyPI version badge for {dist!r}; add "
        f"![PyPI](https://img.shields.io/pypi/v/{dist})"
    )
    assert f"pypi.org/project/{dist}" in README, (
        f"the {dist!r} badge should link to its PyPI project page"
    )
