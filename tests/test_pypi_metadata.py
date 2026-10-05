"""The published metadata is the project's only shop window — keep it complete.

A package can be installable and still be invisible. PyPI indexes
``keywords`` for search, renders ``project.urls`` as the only navigational
links on the landing page, and shows a README badge to tell a visitor which
release is current. Each of those fields was empty or missing here at least
once, so an omission is now a test failure instead of something nobody
notices until the next release is cut.
"""

from __future__ import annotations

import re
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

# PyYAML is already a runtime dependency, so the workflow needs no new parser.
CI_WORKFLOW = yaml.safe_load(
    (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
)


def _classifier_versions() -> list[str]:
    """Per-minor-version classifiers only: the bare `:: 3` row is not a version."""
    prefix = "Programming Language :: Python :: "
    return [
        v
        for c in PROJECT.get("classifiers") or []
        if c.startswith(prefix) and (v := c.removeprefix(prefix)) and v[0].isdigit() and "." in v
    ]


def _required_versions() -> set[str]:
    """Versions implied by the manifest: floor from ``requires-python``, ceiling
    from the highest classifier declared.

    Derived, not hand-written. A literal like ``{"3.10", "3.11", "3.12", "3.13"}``
    cannot notice a version missing from that literal, which is how 3.13 was
    absent from the classifiers while the suite stayed green and
    ``requires-python = ">=3.10"`` claimed it.
    """
    floor_match = re.search(r">=(\d+)\.(\d+)", PROJECT["requires-python"])
    assert floor_match, f"cannot read a floor from requires-python {PROJECT['requires-python']!r}"
    floor = tuple(int(part) for part in floor_match.groups())
    ceiling = max(tuple(int(p) for p in v.split(".")) for v in _classifier_versions())
    # CPython minor versions are contiguous within a major, so the run from
    # (major, minor) floor to (major, minor) ceiling is a simple count.
    assert floor[0] == ceiling[0], f"range spans majors: {floor} to {ceiling}"
    return {f"{floor[0]}.{minor}" for minor in range(floor[1], ceiling[1] + 1)}


def _matrix_versions() -> list[str]:
    job = CI_WORKFLOW["jobs"]["test"]
    return [str(v) for v in job["strategy"]["matrix"]["python-version"]]


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


def test_classifiers_and_ci_matrix_agree() -> None:
    """A version claimed but never tested is the dangerous kind of claim.

    PyPI filters its version selector by classifier, so a `Programming Language ::
    Python :: 3.14` row is a promise that 3.14 works. If CI does not run that leg,
    the promise is unfalsified. Conversely a matrix leg with no classifier makes
    the support invisible to anyone filtering by version. The two lists must be
    the same set.
    """
    classified, tested = set(_classifier_versions()), set(_matrix_versions())
    assert classified, "no per-version Python classifiers declared"
    assert classified == tested, (
        f"classifiers claim {sorted(classified)} but CI tests {sorted(tested)}; "
        "a version advertised on PyPI is an untested claim, and a tested version "
        "missing a classifier is hidden from the PyPI filter"
    )


def test_the_declared_versions_are_a_contiguous_run() -> None:
    """No hole between the ``requires-python`` floor and the newest classifier.

    ``requires-python = ">=3.10"`` together with a ``3.14`` classifier *implies*
    3.11, 3.12 and 3.13: pip installs this package on each. Every version in
    that interval must be classified (or PyPI's version filter hides it) and on
    a CI leg (or the claim is untested).

    Deriving the set from both ends of the range is what makes this catch the
    real bug. ``test_classifiers_and_ci_matrix_agree`` compares two hand-typed
    lists, so dropping 3.13 out of *both* left it passing -- the blind spot that
    let the gap ship in the first place.
    """
    required = _required_versions()
    declared = set(_classifier_versions())
    missing = sorted(required - declared, key=lambda v: tuple(int(p) for p in v.split(".")))
    assert not missing, (
        f"Python {missing} is installable (requires-python {PROJECT['requires-python']!r}) "
        f"and sits below the newest declared classifier, but carries no "
        f"Programming Language :: Python :: classifier, so PyPI's version filter "
        f"hides the package from users on {missing[0]}"
    )
    assert not (declared - required), (
        f"classifiers declare {sorted(declared - required)}, which requires-python "
        f"{PROJECT['requires-python']!r} does not permit installing"
    )


def test_requires_python_covers_every_advertised_version() -> None:
    """`requires-python` is the install gate; a narrower range voids the classifiers."""
    assert PROJECT["requires-python"] == ">=3.10", (
        f"requires-python is {PROJECT['requires-python']!r}; a floor above 3.10 "
        f"would void the {sorted(_classifier_versions())} classifiers still "
        "advertised on PyPI"
    )


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
