#!/usr/bin/env python3
"""Install (or remove) the retrieval-quality synonyms into Typesense.

Reads ``synonyms.json`` in this directory and upserts each entry into the
``papers`` collection's synonyms API. With ``--remove``, deletes each entry
by ID — useful when running a clean-baseline evaluation.

Env vars required (same as the rest of the project):

    TYPESENSE_HOST, TYPESENSE_PORT, TYPESENSE_PROTOCOL,
    TYPESENSE_ADMIN_API_KEY

Usage::

    python install_synonyms.py              # upsert all synonyms
    python install_synonyms.py --remove     # delete all synonyms by id
    python install_synonyms.py --file my_synonyms.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "search" / "scripts"))

try:
    from typesense_client import get_client  # type: ignore
except Exception as e:  # pragma: no cover
    print(f"Could not import typesense_client: {e}", file=sys.stderr)
    print(
        "Make sure search/scripts/typesense_client.py is present and env is configured.",
        file=sys.stderr,
    )
    sys.exit(2)


COLLECTION = "papers"


def load_synonyms(path: Path) -> list[dict[str, Any]]:
    with path.open() as f:
        data = json.load(f)
    syn = data.get("synonyms") or []
    # Strip the document-level `_comment` if someone added one at the item
    # level by mistake.
    return [s for s in syn if isinstance(s, dict) and s.get("id")]


def _to_payload(entry: dict[str, Any]) -> dict[str, Any]:
    """Build a Typesense synonyms payload from a single entry.

    Typesense accepts either ``{"synonyms": [...]}`` (multi-way) or
    ``{"root": "...", "synonyms": [...]}`` (one-way). We preserve whatever
    the author encoded in the JSON.
    """
    payload: dict[str, Any] = {"synonyms": entry["synonyms"]}
    if "root" in entry and entry["root"]:
        payload["root"] = entry["root"]
    if "locale" in entry and entry["locale"]:
        payload["locale"] = entry["locale"]
    return payload


def install(client, entries: list[dict[str, Any]]) -> int:
    ok = 0
    for entry in entries:
        sid = entry["id"]
        payload = _to_payload(entry)
        try:
            client.collections[COLLECTION].synonyms.upsert(sid, payload)
            root = entry.get("root") or "(multi-way)"
            print(f"  + {sid:30s} root={root!r:30s} syns={len(entry['synonyms'])}")
            ok += 1
        except Exception as e:  # pragma: no cover — network path
            print(f"  ! {sid}: {e}", file=sys.stderr)
    return ok


def remove(client, entries: list[dict[str, Any]]) -> int:
    ok = 0
    for entry in entries:
        sid = entry["id"]
        try:
            client.collections[COLLECTION].synonyms[sid].delete()
            print(f"  - {sid}")
            ok += 1
        except Exception as e:  # pragma: no cover — network path
            print(f"  ! {sid}: {e}", file=sys.stderr)
    return ok


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--file", default=str(_HERE / "synonyms.json"), help="Path to synonyms JSON")
    p.add_argument("--remove", action="store_true", help="Delete synonyms instead of upserting")
    args = p.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        print(f"Synonyms file not found: {path}", file=sys.stderr)
        return 2

    entries = load_synonyms(path)
    if not entries:
        print(f"No synonym entries in {path}", file=sys.stderr)
        return 2

    client = get_client()

    # Sanity check — collection must exist before we can attach synonyms to it.
    try:
        client.collections[COLLECTION].retrieve()
    except Exception as e:
        print(f"Could not retrieve `{COLLECTION}` collection: {e}", file=sys.stderr)
        return 2

    if args.remove:
        print(f"Removing {len(entries)} synonym entries from `{COLLECTION}`...")
        ok = remove(client, entries)
        print(f"Removed: {ok}/{len(entries)}")
    else:
        print(f"Upserting {len(entries)} synonym entries into `{COLLECTION}`...")
        ok = install(client, entries)
        print(f"Upserted: {ok}/{len(entries)}")
    return 0 if ok == len(entries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
