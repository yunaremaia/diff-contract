"""CLI entry point for diff-contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from diff_contract import __version__
from diff_contract.contract import load_contract
from diff_contract.engine import DiffCalculator, RulesEngine, Violation, ViolationSeverity
from diff_contract.sarif import violations_to_sarif


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="diff-contract",
        description="Deterministic guardrails for AI-generated diffs",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # `check` command
    check_parser = subparsers.add_parser("check", help="Check diff against contract")
    check_parser.add_argument(
        "--contract",
        type=Path,
        default=Path(".diffcontract.yml"),
        help="Path to .diffcontract.yml (default: .diffcontract.yml)",
    )
    check_parser.add_argument(
        "--base",
        default="main",
        help="Base branch to diff against (default: main)",
    )
    check_parser.add_argument(
        "--output",
        choices=["json", "text"],
        default="text",
        help="Output format (default: text)",
    )
    check_parser.add_argument(
        "--sarif",
        action="store_true",
        help="Output SARIF 2.1.0 format for GitHub Code Scanning",
    )
    check_parser.add_argument(
        "--files",
        nargs="*",
        help="Specific files to check (instead of git diff)",
    )

    # `validate` command (no git dependency)
    validate_parser = subparsers.add_parser("validate", help="Validate files against contract (no git required)")
    validate_parser.add_argument(
        "--contract",
        type=Path,
        default=Path(".diffcontract.yml"),
        help="Path to .diffcontract.yml (default: .diffcontract.yml)",
    )
    validate_parser.add_argument(
        "--files",
        nargs="*",
        help="Files to validate",
    )
    validate_parser.add_argument(
        "--from-stdin",
        action="store_true",
        help="Read file list from stdin (one per line)",
    )
    validate_parser.add_argument(
        "--output",
        choices=["json", "text"],
        default="text",
        help="Output format (default: text)",
    )
    validate_parser.add_argument(
        "--sarif",
        action="store_true",
        help="Output SARIF 2.1.0 format for GitHub Code Scanning",
    )

    # `init` command
    init_parser = subparsers.add_parser("init", help="Create a sample .diffcontract.yml")
    init_parser.add_argument(
        "--template",
        choices=["python", "react", "django", "rust", "docs"],
        default="python",
        help="Template type (default: python)",
    )

    args = parser.parse_args(argv)

    if args.command == "check":
        return _cmd_check(args)
    elif args.command == "validate":
        return _cmd_validate(args)
    elif args.command == "init":
        return _cmd_init(args.template)
    else:
        parser.print_help()
        return 1


def _cmd_check(args: argparse.Namespace) -> int:
    """Execute the check command."""
    # Load contract
    contract_path: Path = args.contract
    if not contract_path.exists():
        print(f"ERROR: Contract not found: {contract_path}", file=sys.stderr)
        return 1

    contract = load_contract(contract_path)

    # Get changed files
    if args.files:
        changed_files: list = list(args.files)
    else:
        calc = DiffCalculator(base_branch=args.base)
        changed_files = calc.get_changed_files()

    # Validate
    engine = RulesEngine(contract.rules)
    violations = engine.check(changed_files)

    # Output
    if args.sarif:
        sarif_doc = violations_to_sarif(violations)
        print(json.dumps(sarif_doc, indent=2))
    elif args.output == "json":
        result = {
            "clean": len(violations) == 0,
            "block_count": sum(1 for v in violations if v.severity == ViolationSeverity.BLOCK),
            "warn_count": sum(1 for v in violations if v.severity == ViolationSeverity.WARN),
            "violations": [
                {
                    "file": v.file,
                    "severity": v.severity.value,
                    "rule": v.rule,
                    "message": v.message,
                }
                for v in violations
            ],
        }
        print(json.dumps(result, indent=2))
    else:
        if not violations:
            print("✓ Diff is clean — no contract violations")
        else:
            print(f"✗ {len(violations)} violation(s):")
            for v in violations:
                icon = "🔴" if v.severity == ViolationSeverity.BLOCK else "🟡"
                print(f"  {icon} [{v.severity.value.upper()}] {v.message}")

    # Exit code
    has_block = any(v.severity == ViolationSeverity.BLOCK for v in violations)
    has_warn = any(v.severity == ViolationSeverity.WARN for v in violations)
    if has_block:
        return 1
    elif has_warn:
        return 2
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    """Execute the validate command (no git dependency)."""
    contract_path: Path = args.contract
    if not contract_path.exists():
        print(f"ERROR: Contract not found: {contract_path}", file=sys.stderr)
        return 1

    contract = load_contract(contract_path)

    # Get changed files
    if args.from_stdin:
        changed_files = [line.strip() for line in sys.stdin if line.strip()]
    elif args.files:
        changed_files = list(args.files)
    else:
        print("ERROR: Provide --files or --from-stdin", file=sys.stderr)
        return 1

    # Validate
    engine = RulesEngine(contract.rules)
    violations = engine.check(changed_files)

    # Output
    if args.sarif:
        sarif_doc = violations_to_sarif(violations)
        print(json.dumps(sarif_doc, indent=2))
    elif args.output == "json":
        result = {
            "clean": len(violations) == 0,
            "block_count": sum(1 for v in violations if v.severity == ViolationSeverity.BLOCK),
            "warn_count": sum(1 for v in violations if v.severity == ViolationSeverity.WARN),
            "violations": [
                {
                    "file": v.file,
                    "severity": v.severity.value,
                    "rule": v.rule,
                    "message": v.message,
                }
                for v in violations
            ],
        }
        print(json.dumps(result, indent=2))
    else:
        if not violations:
            print("✓ Diff is clean — no contract violations")
        else:
            print(f"✗ {len(violations)} violation(s):")
            for v in violations:
                icon = "🔴" if v.severity == ViolationSeverity.BLOCK else "🟡"
                print(f"  {icon} [{v.severity.value.upper()}] {v.message}")

    # Exit codes: 0 clean, 1 block, 2 warn
    has_block = any(v.severity == ViolationSeverity.BLOCK for v in violations)
    has_warn = any(v.severity == ViolationSeverity.WARN for v in violations)
    if has_block:
        return 1
    elif has_warn:
        return 2
    return 0


def _cmd_init(template_type: str = "python") -> int:
    """Create a sample .diffcontract.yml from a template."""
    template = _TEMPLATES.get(template_type, _TEMPLATES["python"])
    path = Path(".diffcontract.yml")
    if path.exists():
        print(f"WARNING: {path} already exists — not overwriting", file=sys.stderr)
        return 1
    path.write_text(template)
    print(f"✓ Created {path} (template: {template_type})")
    return 0


_TEMPLATES = {
    "python": """# .diffcontract.yml — Python project contract
version: 1

rules:
  # Block changes to critical infrastructure
  - name: "Protect CI/CD configs"
    deny:
      - ".github/workflows/*.yml"
      - "Dockerfile"
      - "docker-compose.yml"
    on_violation: block

  # Allow feature work with limits
  - name: "Feature development"
    allow:
      - "src/features/**"
      - "tests/features/**"
    max_files: 15
    max_lines: 400
    on_violation: block

  # Warn on large diffs
  - name: "Large diff warning"
    max_files: 20
    max_lines: 500
    on_violation: warn
""",
    "react": """# React/Next.js project contract
version: 1

rules:
  - name: "Protect CI/CD configs"
    deny:
      - ".github/workflows/*.yml"
      - "Dockerfile"
      - "docker-compose.yml"
    on_violation: block

  - name: "Protect root config"
    deny:
      - "package.json"
      - "package-lock.json"
      - "tsconfig.json"
      - "next.config.*"
      - ".env*"
    on_violation: block

  - name: "Feature development"
    allow:
      - "app/**"
      - "components/**"
      - "lib/**"
      - "pages/**"
      - "src/**"
      - "styles/**"
      - "public/**"
    max_files: 20
    max_lines: 600
    on_violation: block

  - name: "Test updates"
    allow:
      - "tests/**"
      - "__tests__/**"
      - "*.test.*"
      - "*.spec.*"
    max_files: 10
    max_lines: 300
    on_violation: warn
""",
    "django": """# Django project contract
version: 1

rules:
  - name: "Protect deployment configs"
    deny:
      - "Dockerfile"
      - "docker-compose.yml"
      - ".github/workflows/*.yml"
      - "requirements/base.txt"
    on_violation: block

  - name: "Protect root config"
    deny:
      - "manage.py"
      - "project/settings/*.py"
      - "pyproject.toml"
      - "requirements/*.txt"
    on_violation: block

  - name: "Feature development"
    allow:
      - "apps/**"
      - "templates/**"
      - "static/**"
      - "media/**"
    max_files: 15
    max_lines: 500
    on_violation: block

  - name: "Test updates"
    allow:
      - "tests/**"
      - "**/tests.py"
      - "**/test_*.py"
    max_files: 10
    max_lines: 200
    on_violation: warn
""",
    "rust": """# Rust workspace contract
version: 1

rules:
  - name: "Protect CI/CD configs"
    deny:
      - ".github/workflows/*.yml"
      - "Dockerfile"
      - "docker-compose.yml"
      - "rust-toolchain.toml"
    on_violation: block

  - name: "Protect workspace config"
    deny:
      - "Cargo.toml"
      - "Cargo.lock"
      - "deny.toml"
      - "clippy.toml"
      - "rustfmt.toml"
    on_violation: block

  - name: "Feature development"
    allow:
      - "crates/**"
      - "src/**"
      - "tests/**"
      - "benches/**"
      - "examples/**"
    max_files: 15
    max_lines: 500
    on_violation: block

  - name: "Test updates"
    allow:
      - "tests/**"
      - "**/tests/*.rs"
      - "**/tests/**/*.rs"
      - "benches/**"
    max_files: 10
    max_lines: 200
    on_violation: warn
""",
    "docs": """# Documentation-only project contract
version: 1

rules:
  - name: "Block source code changes"
    deny:
      - "src/**"
      - "lib/**"
      - "app/**"
      - "packages/**"
      - "*.py"
      - "*.js"
      - "*.ts"
      - "*.rs"
      - "*.go"
    on_violation: block

  - name: "Documentation updates"
    allow:
      - "docs/**"
      - "*.md"
      - "*.rst"
      - "CHANGELOG*"
      - "LICENSE*"
      - "README*"
    max_files: 30
    max_lines: 1000
    on_violation: block
""",
}



if __name__ == "__main__":
    sys.exit(main())
