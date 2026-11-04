"""Shared helpers for the Pharma Access Atlas pipeline.

Everything here uses only the Python standard library, so the pipeline
runs anywhere Python 3.9+ is installed, with nothing to pip-install.
"""
from __future__ import annotations

import csv
import hashlib
import json
import time
import urllib.request
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Folder layout (all paths are relative to the repository root)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
MANUAL = ROOT / "data" / "manual"
PROCESSED = ROOT / "data" / "processed"
CACHE = ROOT / "data" / "cache"  # large downloads; ignored by git

# Every manual CSV uses this exact header.
MANUAL_HEADER = ["drug_id", "field", "value", "status", "source_url", "retrieved_date", "notes"]

# What a value's "status" may be:
#   verified             - value confirmed on the source page
#   not_reimbursed_as_of - we checked: access has NOT happened yet (real information)
#   not_assessed         - we checked: no assessment exists (e.g. exempt from AMNOG)
#   unknown              - not yet checked or could not be verified (shown as a gap)
#   calculated           - derived by the pipeline from other sourced values
MANUAL_STATUSES = {"verified", "not_reimbursed_as_of", "not_assessed", "unknown"}

USER_AGENT = "PharmaAccessAtlas/1.0 (public research portfolio; https://github.com/)"


def today() -> str:
    return date.today().isoformat()


def http_get(url: str, retries: int = 3, pause: float = 2.0) -> bytes:
    """Download a URL politely: identify ourselves and retry a few times."""
    last_error = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except Exception as exc:  # network hiccups, 5xx, timeouts
            last_error = exc
            time.sleep(pause * (attempt + 1))
    raise RuntimeError(f"Could not download {url}: {last_error}")


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=False)
        f.write("\n")


def load_drugs() -> list[dict]:
    """The curated drug list (data/manual/drugs.csv) drives everything."""
    return read_csv(MANUAL / "drugs.csv")


# ---------------------------------------------------------------------------
# Raw-file manifest
# ---------------------------------------------------------------------------
# For each raw file we remember when its *current content* was first retrieved.
# If a monthly refresh downloads identical content, the date stays the same,
# so nothing changes and nothing gets committed.
MANIFEST = RAW / "manifest.json"


def save_raw(relative: str, content: bytes, source_url: str) -> str:
    """Write a raw file and return the retrieved_date for its content."""
    path = RAW / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    digest = hashlib.sha256(content).hexdigest()
    entry = manifest.get(relative)
    if entry and entry["sha256"] == digest and path.exists():
        return entry["retrieved_date"]  # unchanged: keep the original date
    path.write_bytes(content)
    manifest[relative] = {"sha256": digest, "retrieved_date": today(), "source_url": source_url}
    MANIFEST.write_text(json.dumps(dict(sorted(manifest.items())), indent=2) + "\n")
    return manifest[relative]["retrieved_date"]


def raw_retrieved_date(relative: str) -> str | None:
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    entry = manifest.get(relative)
    return entry["retrieved_date"] if entry else None
