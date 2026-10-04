"""diff-contract — deterministic guardrails for ai-generated diffs."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _metadata_version

from diff_contract.engine import GitDiffError

try:
    __version__ = _metadata_version("diff-contract")
except PackageNotFoundError:  # running from a source checkout, not an install
    __version__ = "0.0.0.dev0"

__all__ = ["__version__", "GitDiffError"]
