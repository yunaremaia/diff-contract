"""SARIF 2.1.0 output for diff-contract."""

from __future__ import annotations

import json
from typing import Any

from diff_contract.engine import Violation


def violations_to_sarif(
    violations: list[Violation],
    tool_name: str = "diff-contract",
    tool_version: str = "0.1.0",
) -> dict[str, Any]:
    """Convert violations to SARIF 2.1.0 format.

    Args:
        violations: List of Violation objects from RulesEngine
        tool_name: Tool name for SARIF runner
        tool_version: Tool version for SARIF runner

    Returns:
        SARIF 2.1.0 document as dict
    """
    rules = []
    results = []

    # Build rules from unique violation types
    rule_ids = set()
    for v in violations:
        rule_id = f"diff-contract/{v.rule}"
        if rule_id not in rule_ids:
            rule_ids.add(rule_id)
            rules.append(
                {
                    "id": rule_id,
                    "name": v.rule,
                    "shortDescription": {
                        "text": f"Contract rule: {v.rule}",
                    },
                    "fullDescription": {
                        "text": f"Violates diff-contract rule '{v.rule}'. File: {v.file}",
                    },
                    "defaultConfiguration": {
                        "level": "error"
                        if v.severity.value == "block"
                        else "warning",
                    },
                }
            )

    # Build results
    for v in violations:
        level = "error" if v.severity.value == "block" else "warning"
        results.append(
            {
                "ruleId": f"diff-contract/{v.rule}",
                "level": level,
                "message": {"text": v.message},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {
                                "uri": v.file,
                            },
                        },
                    }
                ],
            }
        )

    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": tool_name,
                        "version": tool_version,
                        "informationUri": "https://github.com/yunaremaia/diff-contract",
                        "rules": rules,
                    },
                },
                "results": results,
            }
        ],
    }


def sarif_to_string(sarif_doc: dict[str, Any]) -> str:
    """Serialize SARIF document to JSON string."""
    return json.dumps(sarif_doc, indent=2)
