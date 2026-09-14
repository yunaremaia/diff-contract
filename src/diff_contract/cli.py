"""CLI entry point for diff-contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from diff_contract import __version__
from diff_contract.contract import load_contract
from diff_contract.engine import DiffCalculator, RulesEngine, ViolationSeverity


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

    # `init` command
    init_parser = subparsers.add_parser("init", help="Create a sample .diffcontract.yml")

    args = parser.parse_args(argv)

    if args.command == "check":
        return _cmd_check(args)
    elif args.command == "validate":
        return _cmd_validate(args)
    elif args.command == "init":
        return _cmd_init()
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
    if args.output == "json":
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
    if args.output == "json":
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


def _cmd_init() -> int:
    """Create a sample .diffcontract.yml."""
    sample = """# .diff-contract.yml — Define allowed/denied file patterns for diffs
version: 1

rules:
  # Block changes to core files
  - name: "Block core changes"
    deny:
      - "src/core/**"
      - "config/*.env"
    on_violation: block

  # Allow feature changes
  - name: "Allow feature X"
    allow:
      - "src/features/X/**"
      - "tests/features/X/**"
    on_violation: block

  # Warn on large diffs
  - name: "Large diff warning"
    max_files: 20
    max_lines: 500
    on_violation: warn
"""
    path = Path(".diffcontract.yml")
    if path.exists():
        print(f"WARNING: {path} already exists — not overwriting", file=sys.stderr)
        return 1
    path.write_text(sample)
    print(f"✓ Created {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
