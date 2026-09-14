# Contributing to diff-contract

Thank you for your interest in contributing!

## Development Setup

**Requirements:**
- Python 3.10+
- pip or uv

**Setup:**

```bash
git clone https://github.com/yunaremaia/diff-contract.git
cd diff-contract
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest -q                              # run all tests
pytest tests/test_cli.py               # run specific test file
pytest -q --cov=diff_contract --cov-report=term-missing  # with coverage
```

## Project Structure

```
diff-contract/
├── src/diff_contract/
│   ├── cli.py          # CLI interface
│   ├── contract.py     # Contract definition and validation
│   ├── engine.py       # Diff engine
│   └── validate.py     # Validation logic
├── tests/              # Test suite (4 test files)
├── .github/workflows/  # CI/CD
└── pyproject.toml      # Build config
```

## Code Style

- Formatter: `ruff format`
- Linter: `ruff check`
- Type hints: encouraged on all functions

## PR Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make your changes, add tests
4. Run tests: `pytest -q`
5. Commit, push, and open a PR
6. CI will run automatically

## Commit Messages

We follow Conventional Commits:
- `feat: add new contract type`
- `fix: handle edge case in validation`
- `docs: update README`
- `test: add coverage for engine`

## Release Process

Releases are automated via GitHub Actions:
1. Version bumped in `pyproject.toml`
2. Tag `v0.1.X` pushed
3. `publish.yml` publishes to PyPI

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
