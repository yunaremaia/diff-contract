"""Regression guard for the documentation site's SEO and social metadata.

The published HTML of the site contained no <meta name="description"> and no
Open Graph / Twitter Card tags. This test ensures that does not regress.

The expected values are derived from pyproject.toml, not hardcoded, so a
hand-written list cannot miss the thing that is actually missing.
"""

from __future__ import annotations

import re
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parents[1]
MKDOCS_YML = REPO_ROOT / "mkdocs.yml"
OVERRIDES_DIR = REPO_ROOT / "overrides"
OVERRIDES_MAIN = OVERRIDES_DIR / "main.html"

PROJECT = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
EXPECTED_DESCRIPTION = PROJECT["description"]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_site_description_is_set_in_mkdocs_yml() -> None:
    """site_description must be present in mkdocs.yml.

    Without it mkdocs builds green but emits no <meta name="description"> tag.
    """
    content = _read_text(MKDOCS_YML)
    match = re.search(r"^site_description:\s*(.+)$", content, re.MULTILINE)
    assert match, (
        "mkdocs.yml has no site_description; the built HTML will lack "
        "<meta name=\"description\"> and search engines will show no snippet"
    )
    actual = match.group(1).strip().strip('"').strip("'")
    assert actual == EXPECTED_DESCRIPTION, (
        f"site_description in mkdocs.yml is {actual!r} but pyproject.toml "
        f"declares {EXPECTED_DESCRIPTION!r}"
    )


def test_custom_dir_is_configured() -> None:
    """theme.custom_dir must point to the overrides directory."""
    content = _read_text(MKDOCS_YML)
    match = re.search(r"^\s+custom_dir:\s*(\S+)", content, re.MULTILINE)
    assert match, (
        "mkdocs.yml theme has no custom_dir; the overrides/main.html template "
        "will not be loaded and no og:/twitter: tags will be emitted"
    )
    custom_dir = match.group(1)
    assert (REPO_ROOT / custom_dir / "main.html").is_file(), (
        f"custom_dir {custom_dir!r} does not contain main.html"
    )


def test_overrides_main_html_exists() -> None:
    """The overrides/main.html file must exist and be tracked by git."""
    assert OVERRIDES_MAIN.is_file(), (
        f"{OVERRIDES_MAIN} does not exist; the og:/twitter: tags will not be emitted"
    )


def test_overrides_references_og_title() -> None:
    """overrides/main.html must reference og:title."""
    content = _read_text(OVERRIDES_MAIN)
    assert "og:title" in content, (
        "overrides/main.html does not reference og:title; "
        "social link previews will have no title"
    )


def test_overrides_references_og_description() -> None:
    """overrides/main.html must reference og:description."""
    content = _read_text(OVERRIDES_MAIN)
    assert "og:description" in content, (
        "overrides/main.html does not reference og:description; "
        "social link previews will have no description"
    )


def test_overrides_references_og_url() -> None:
    """overrides/main.html must reference og:url."""
    content = _read_text(OVERRIDES_MAIN)
    assert "og:url" in content, (
        "overrides/main.html does not reference og:url; "
        "social link previews will have no canonical URL"
    )


def test_overrides_references_twitter_card() -> None:
    """overrides/main.html must reference twitter:card."""
    content = _read_text(OVERRIDES_MAIN)
    assert "twitter:card" in content, (
        "overrides/main.html does not reference twitter:card; "
        "Twitter/X link previews will not render"
    )


def test_overrides_uses_site_description() -> None:
    """overrides/main.html must use config.site_description for og:description."""
    content = _read_text(OVERRIDES_MAIN)
    assert "site_description" in content, (
        "overrides/main.html does not use config.site_description; "
        "og:description will not match the package description"
    )


def test_overrides_uses_canonical_url() -> None:
    """overrides/main.html must use page.canonical_url for og:url."""
    content = _read_text(OVERRIDES_MAIN)
    assert "canonical_url" in content, (
        "overrides/main.html does not use page.canonical_url; "
        "og:url will not point to the correct page"
    )
