"""Run the whole pipeline in order: fetch -> build -> validate -> coverage.

    python3 pipeline/run_all.py            # full refresh (downloads data)
    python3 pipeline/run_all.py --offline  # rebuild from files already in data/raw

Stops with an error if validation fails, so bad data never reaches the site.
"""
from __future__ import annotations

import sys

import build
import coverage
import fetch_cms
import fetch_ema
import fetch_fda
import fetch_france
import validate


def main() -> int:
    if "--offline" not in sys.argv:
        print("1/4 Fetching sources")
        fetch_fda.main()
        fetch_ema.main()
        fetch_cms.main()
        fetch_france.main()
    print("2/4 Building data/processed/drugs.json")
    build.main()
    print("3/4 Validating")
    if validate.main() != 0:
        print("Validation failed: fix the errors above before publishing.")
        return 1
    print("4/4 Coverage")
    coverage.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
