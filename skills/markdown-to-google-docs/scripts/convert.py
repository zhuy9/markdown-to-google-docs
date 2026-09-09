"""Invoke the same engine from a checkout or a generated skill archive."""

from pathlib import Path
import sys

here = Path(__file__).resolve().parent
sys.path.insert(0, str(here if (here / "md2gdoc").is_dir() else here.parents[2] / "src"))

from md2gdoc.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
