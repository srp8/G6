"""Thin wrapper so `python benchmark/run_benchmark.py ...` keeps working.

All logic lives in minicodex/bench.py (also installed as `minicodex-bench`).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from minicodex.bench import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
