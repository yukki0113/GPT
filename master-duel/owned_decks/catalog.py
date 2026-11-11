"""Private owned-deck catalog v1; validation and lookup only.

No Google Drive transport, no user inventory updates, and no writes to
the production Master Duel database.
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import unicodedata
from pathlib import Path

SCHEMA = "md-owned-deck-catalog-v1"
SNAPSHOT_SCHEMA = "md-owned-deck-v1"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
STATES = {"STAGED", "CONFIRMED"}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def empty_catalog(timestamp):
    result = {"schema": SCHEMA, "generation": 1, "updated_at": timestamp, "decks": []}
    validate(result)
    return result


def _string(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(field + " must be a nonempty string")
    return value


def _sha(value, field):
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        raise ValueError(field + " must be lowercase SHA256")
    return value


def _timestamp(value):
    _string(value, "updated_at")
    if not value.endswith("Z"):
        raise ValueError("updated_at must be UTC with Z suffix")
    try:
        dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("updated_at must be ISO8601") from exc


def _aliases(value):
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise ValueError("aliases must be a list of nonempty strings")
    if len(set(_key(x) for x in value)) != len(value):
        raise ValueError("duplicate aliases")


def _key(value):
    return "".join(unicodedata.normalize("NFKC", value).casefold().split())


def validate(catalog):
    """Fail closed on broken relationships. Returns public-safe summary only."""
    if not isinstance(catalog, dict) or catalog.get("schema") != SCHEMA:
        raise ValueError("invalid catalog schema")
    generation = catalog.get("generation")
    if type(generation) is not int or generation < 1:
        raise ValueError("generation must be positive integer")
    _timestamp(catalog.get("updated_at"))
    decks = catalog.get("decks")
    if not isinstance(decks, list):
        raise ValueError("decks must be a list")
    ids = set()
    all_files = set()
    for deck in decks:
        if not isinstance(deck, dict):
            raise ValueError("invalid deck")
        deck_id = _string(deck.get("deck_id"), "deck_id")
        if deck_id in ids:
            raise ValueError("duplicate deck_id")
        ids.add(deck_id)
        _string(deck.get("name"), "name")
        _aliases(deck.get("aliases", []))
        variant = deck.get("variant")
        if variant is not None:
            _string(variant, "variant")
        versions = deck.get("versions")
        if not isinstance(versions, list) or not versions:
            raise ValueError("catalog deck needs at least one version")
        previous = None
        for number, item in enumerate(versions, 1):
            if not isinstance(item, dict) or type(item.get("version")) is not int or item["version"] != number:
                raise ValueError("versions must start at 1 and be contiguous")
            if item.get("state") not in STATES:
                raise ValueError("invalid version state")
            digest = _sha(item.get("snapshot_sha256"), "snapshot_sha256")
            file_id = _string(item.get("drive_file_id"), "drive_file_id")
            if file_id in all_files:
                raise ValueError("duplicate drive_file_id")
            all_files.add(file_id)
            if item.get("supersedes") != previous:
                raise ValueError("version supersedes does not match prior snapshot sha")
            previous = digest
    return {"schema": SCHEMA, "generation": generation, "deck_count": len(decks),
            "snapshot_count": sum(len(d["versions"]) for d in decks), "sha256": sha256(catalog)}


def resolve(catalog, query):
    """Return all matching deck variants and the latest CONFIRMED pointer."""
    validate(catalog)
    q = _key(_string(query, "query"))
    matches = []
    for deck in catalog["decks"]:
        tokens = [deck["deck_id"], deck["name"], *deck.get("aliases", [])]
        if deck.get("variant"):
            tokens.append(deck["variant"])
        if not any(q in _key(item) for item in tokens):
            continue
        confirmed = next((v for v in reversed(deck["versions"]) if v["state"] == "CONFIRMED"), None)
        latest = deck["versions"][-1]
        matches.append({"deck_id": deck["deck_id"], "name": deck["name"],
                        "variant": deck.get("variant"), "latest_version": latest["version"],
                        "latest_state": latest["state"], "confirmed": confirmed})
    return {"query": query, "status": "NOT_FOUND" if not matches else
            "AMBIGUOUS" if len(matches) > 1 else
            "READY" if matches[0]["confirmed"] else "STAGED_ONLY", "matches": matches}


def validate_snapshot_pointer(catalog, snapshot, deck_id, version):
    """Verify a fetched private snapshot is exactly the catalog's declared version."""
    validate(catalog)
    deck = next((d for d in catalog["decks"] if d["deck_id"] == deck_id), None)
    if deck is None or type(version) is not int or not 1 <= version <= len(deck["versions"]):
        raise ValueError("unknown deck version")
    pointer = deck["versions"][version - 1]
    if not isinstance(snapshot, dict) or snapshot.get("schema") != SNAPSHOT_SCHEMA:
        raise ValueError("invalid snapshot")
    for key, expected in (("deck_id", deck_id), ("version", version),
                          ("state", pointer["state"]), ("supersedes", pointer["supersedes"])):
        if snapshot.get(key) != expected:
            raise ValueError("snapshot mismatch: " + key)
    if sha256(snapshot) != pointer["snapshot_sha256"]:
        raise ValueError("snapshot SHA mismatch")
    return pointer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init", "validate", "resolve"])
    parser.add_argument("--input", help="private catalog JSON path")
    parser.add_argument("--timestamp", help="UTC ISO8601 for init")
    parser.add_argument("--name", help="deck name/alias/id to resolve")
    parser.add_argument("--output", help="output path (init only)")
    args = parser.parse_args()
    if args.command == "init":
        if not args.timestamp or not args.output:
            parser.error("init requires --timestamp and --output")
        catalog = empty_catalog(args.timestamp)
        dest = Path(args.output)
        if dest.exists():
            raise ValueError("refusing to overwrite existing catalog")
        dest.write_bytes(canonical(catalog))
        report = validate(json.loads(dest.read_bytes()))
    else:
        if not args.input:
            parser.error("--input required")
        raw = Path(args.input).read_bytes()
        catalog = json.loads(raw)
        report = validate(catalog) if args.command == "validate" else resolve(catalog, args.name)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
