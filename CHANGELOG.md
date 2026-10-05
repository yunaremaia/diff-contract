# Changelog

All notable changes to `diff-contract` are documented here.
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.6] - 2026-10-05

### Added

- `Programming Language :: Python :: 3.13` classifier and a `3.13` leg in the CI test matrix (now 3.10 / 3.11 / 3.12 / 3.13 / 3.14). The classifiers skipped 3.13, so PyPI's version filter hid `diff-contract` from anyone filtering by the Python they actually run, even though the package installs and works there. The classifier is only correct because the full suite was run on CPython 3.13.16 first: 153 passed.

- `tests/test_pypi_metadata.py::test_the_declared_versions_are_a_contiguous_run` derives the expected version set from the `requires-python` floor up to the highest declared classifier. The existing classifier/CI-matrix agreement test compares two hand-maintained lists and therefore cannot fail on a version missing from both — the blind spot that let this gap ship with a green suite.

### Documentation

- Add GitHub issue templates (bug report, feature request) with `blank_issues_enabled: false` and contact links ([#10](https://github.com/yunaremaia/diff-contract/issues/10))
- Add Dependabot configuration for weekly pip dependency updates
- Expand SECURITY.md with supported-versions policy, end-of-life window, and detailed disclosure timeline

## [0.1.4] - 2026-10-05

### Fixed

- **The published pre-commit hook failed on every run.** `.pre-commit-hooks.yaml` declared `entry: diff-contract check`, but `check` takes no positional arguments, so pre-commit's appended staged filenames were rejected by argparse (`unrecognized arguments`, exit 2). Anyone installing the hook with a matching file staged got a hard failure. The entry is now `diff-contract check --files`, which accepts the appended list.

### Changed

- `Homepage` in the packaging metadata now points at the documentation site instead of repeating `Source`, so the two prominent PyPI sidebar slots carry different destinations.

### Added

- `tests/test_precommit_hook.py` parses the real hook manifest and runs the CLI the way pre-commit invokes it, so a manifest that cannot accept appended filenames fails CI instead of failing a user's commit.

## [0.1.3] - 2026-10-05

### Added

- Documentation site published at <https://yunaremaia.github.io/diff-contract/> (MkDocs Material, deployed from `main` via GitHub Pages): install and first run, full CLI reference for `check` / `validate` / `init`, glob-matching and deny-precedence semantics, contract file reference, and CI integration
- `docs` job in CI runs `mkdocs build --strict` and asserts the built sitemap is non-empty before deploying

### Changed

- Add a `Documentation` entry to the project URLs so the PyPI sidebar links to the docs site instead of repeating the repository URL
- Ignore the MkDocs `site/` build output in `.gitignore`

## [0.2.0] - 2026-01-12

### Added

- Project-specific `.diffcontract.yml` templates (examples/)
- `validate`, `init`, and pre-commit hook usage documentation
- `max_files` and `max_lines` aggregate limit documentation

[unreleased]: https://github.com/yunaremaia/diff-contract/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/yunaremaia/diff-contract/compare/v0.1.2...v0.1.3
[0.2.0]: https://github.com/yunaremaia/diff-contract/releases/tag/v0.2.0
