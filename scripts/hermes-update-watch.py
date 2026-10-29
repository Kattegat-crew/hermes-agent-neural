#!/usr/bin/env python3
"""Thin executable for the monitoring-only Hermes update watcher."""

import sys
from pathlib import Path

_SCRIPT_DIRECTORY = str(Path(__file__).resolve().parent)
if _SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, _SCRIPT_DIRECTORY)

from hermes_update_watch.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
