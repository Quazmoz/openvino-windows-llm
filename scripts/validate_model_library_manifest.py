"""Validate the checksummed curated model-library manifest before publication."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.model_library import parse_manifest_bytes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    manifest = parse_manifest_bytes(args.path.read_bytes())
    print(
        f"Validated model library schema {manifest['schema_version']} with "
        f"{len(manifest['catalog'])} curated entries and checksum "
        f"{manifest['catalog_sha256']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
