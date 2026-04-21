"""Create Typesense collections from search/schemas/*.json.

Usage::

    python create_collections.py                  # create if missing
    python create_collections.py --recreate       # drop + create (data loss!)

All schema files in ``search/schemas/`` are processed.  The collection name
is taken from the ``name`` field in the JSON (e.g. ``papers``).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure the scripts directory is on the path (for typesense_client)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from typesense_client import get_client

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"


def load_schemas() -> list[dict]:
    """Read all *.json files from schemas/ and return parsed dicts."""
    schemas = []
    for schema_file in sorted(_SCHEMAS_DIR.glob("*.json")):
        with schema_file.open() as fh:
            schemas.append(json.load(fh))
    return schemas


def create_or_skip(client, schema: dict, recreate: bool = False) -> str:
    """Create the collection; return 'created', 'recreated', or 'skipped'."""
    name = schema["name"]
    existing_names = {c["name"] for c in client.collections.retrieve()}

    if name in existing_names:
        if recreate:
            client.collections[name].delete()
            client.collections.create(schema)
            return "recreated"
        return "skipped"

    client.collections.create(schema)
    return "created"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create THRN Typesense collections")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate existing collections (destroys data!)",
    )
    args = parser.parse_args()

    client = get_client()
    schemas = load_schemas()

    if not schemas:
        print(f"No schemas found in {_SCHEMAS_DIR}", file=sys.stderr)
        sys.exit(1)

    for schema in schemas:
        name = schema.get("name", "?")
        t0 = time.perf_counter()
        action = create_or_skip(client, schema, recreate=args.recreate)
        elapsed = time.perf_counter() - t0
        print(f"  {name}: {action} ({elapsed:.2f}s)")

    print("Done.")


if __name__ == "__main__":
    main()
