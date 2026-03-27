"""CLI subpackage for SHBM.

This package exposes the command-line entrypoints implemented in
`src/cli/bienmuc.py` and `src/cli/metadata.py`.
"""
from .metadata import main as metadata_main
from .bienmuc import main as bienmuc_main

__all__ = ["metadata_main", "bienmuc_main"]
