"""Run directly from a source checkout: python main.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from deepanalyze.server import main

# Optional convenience: set a paper here or use the browser's seed input.
# Leaving this empty opens the workspace without spending model quota.
SEED_PAPER = ""

if __name__ == "__main__":
    arguments = sys.argv[1:]
    if SEED_PAPER and not arguments:
        arguments = ["--seed", SEED_PAPER]
    main(arguments)
