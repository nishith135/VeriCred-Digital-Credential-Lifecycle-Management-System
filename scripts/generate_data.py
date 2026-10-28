"""Convenience script to run the dataset generator from root directory."""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.generator.cli import main

if __name__ == "__main__":
    main()
