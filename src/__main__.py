#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Entry point cho ứng dụng SHBM

This module supports being run both as a package (python -m src) and
as a loose script (python src/__main__.py). When run as a script the
relative import would fail; provide a fallback that adjusts sys.path
and imports `src.gui` using importlib.

This dispatcher chooses which submodule to run based on CLI flags:
  --gui      : start GUI
  --metadata : run metadata CLI (now located at src.cli.metadata)
  --bienmuc  : run bienmuc CLI (now located at src.cli.bienmuc)
"""

import argparse
import sys
import importlib
import os


def main():
    parser = argparse.ArgumentParser(description='SHBM entrypoint dispatcher')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--gui', action='store_true', help='Start the PyQt6 GUI (src.gui)')
    group.add_argument('--metadata', action='store_true', help='Run the metadata CLI (src.cli.metadata)')
    group.add_argument('--bienmuc', action='store_true', help='Run the biên mục CLI (src.cli.bienmuc)')
    # Allow passing through remaining args to the chosen module
    parser.add_argument('remainder', nargs=argparse.REMAINDER, help='Arguments passed to the chosen submodule')

    args = parser.parse_args()

    # If no explicit choice given, show help and exit (safe default)
    if not (args.gui or args.metadata or args.bienmuc):
        parser.print_help()
        sys.exit(0)

    # Adjust sys.argv for the invoked module and import it
    if args.gui:
        # prefer src.gui (if the project provides a dedicated GUI module),
        # but fall back to src.pdf_metadata_gui if not present
        try:
            importlib.import_module('src.gui')
            mod_name = 'src.gui'
        except Exception:
            mod_name = 'src.pdf_metadata_gui'
    elif args.metadata:
        mod_name = 'src.cli.metadata'
    else:
        mod_name = 'src.cli.bienmuc'

    # Prepare new argv for the module: keep program name and the remainder
    new_argv = [mod_name] + args.remainder
    # Insert repo root on sys.path when running as script
    repo_root = os.path.dirname(os.path.dirname(__file__))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    # Import and call the module's main() if available, otherwise use runpy to execute
    try:
        module = importlib.import_module(mod_name)
        if hasattr(module, 'main') and callable(module.main):
            # Set sys.argv to simulate direct module invocation
            old_argv = sys.argv
            try:
                sys.argv = new_argv
                module.main()
            finally:
                sys.argv = old_argv
        else:
            # Fallback: execute the module as a script
            import runpy
            runpy.run_module(mod_name, run_name='__main__')
    except Exception:
        # Re-raise exception so the caller sees the full traceback
        raise


if __name__ == '__main__':
    main()