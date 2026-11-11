"""Private voice-deck snapshots. No Drive transport and no inventory writes."""
import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path

SCHEMA = "md-owned-deck-v1"
STATES = {"STAGED", "CONFIRMED"}
SECTIONS = {"MAIN", "EXTRA"}


def canonical(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(payload):
    return hashlib.sha256(canonical(payload)).hexdigest()


def check(payload, db_path=None):
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ValueError("invalid schema")
    if not isinstance(payload.get("deck_id"), str) or not payload["deck_id"].strip():
        raise ValueError("deck_id required")
    if not isinstance(payload.get("name"), str) or not payload["name"].strip():
        raise ValueError("name required")
    if type(payload.get("version")) is not int or payload["version"] < 1:
        raise ValueError("version must be positive integer")
    if payload.get("state") not in STATES:
        raise ValueError("invalid state")
    if payload["version"] == 1 and payload.get("supersedes") is not None:
        raise ValueError("first version cannot supersede")
    if payload["version"] > 1 and not isinstance(payload.get("supersedes"), str):
        raise ValueError("later version must supersede snapshot hash")
    rows = payload.get("entries")
    if not isinstance(rows, list) or not rows:
        raise ValueError("entries required")
    keyset = set()
    totals = {"MAIN": 0, "EXTRA": 0}
    pending = []
    known_ids = set()
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("section") not in SECTIONS:
            raise ValueError(f"invalid section at {i}")
        quantity = row.get("quantity")
        if type(quantity) is not int or not 1 <= quantity <= 99:
            raise ValueError(f"invalid quantity at {i}")
        if not isinstance(row.get("spoken_name"), str) or not row["spoken_name"].strip():
            raise ValueError(f"spoken_name required at {i}")
        card_id = row.get("card_id")
        if card_id is not None and (not isinstance(card_id, str) or not card_id.strip()):
            raise ValueError(f"invalid card_id at {i}")
        if payload["state"] == "CONFIRMED" and not card_id:
            raise ValueError("confirmed deck contains unresolved card")
        if card_id:
            key = (row["section"], card_id)
            if key in keyset:
                raise ValueError("duplicate section/card ID; merge with source lines retained")
            keyset.add(key)
            known_ids.add(card_id)
        else:
            pending.append(i)
        totals[row["section"]] += quantity
    if db_path:
        with sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True) as connection:
            if known_ids:
                placeholders = ",".join("?" * len(known_ids))
                found = {r[0]: r[1] for r in connection.execute(
                    f"SELECT card_id,name FROM cards WHERE card_id IN ({placeholders})", tuple(known_ids))}
                missing = known_ids - found.keys()
                if missing:
                    raise ValueError("unknown card_id: " + ", ".join(sorted(missing)))
    warnings = []
    if totals["MAIN"] < 40 or totals["MAIN"] > 60:
        warnings.append("MAIN_OUTSIDE_40_60")
    if totals["EXTRA"] > 15:
        warnings.append("EXTRA_OVER_15")
    if pending:
        warnings.append("UNRESOLVED_CARDS")
    if payload["state"] == "CONFIRMED" and warnings:
        raise ValueError("cannot confirm incomplete deck: " + ", ".join(warnings))
    return {"deck_id": payload["deck_id"], "name": payload["name"], "version": payload["version"],
            "state": payload["state"], "main": totals["MAIN"], "extra": totals["EXTRA"],
            "unresolved_indices": pending, "warnings": warnings, "sha256": digest(payload)}


def put(directory, payload, db_path=None):
    report = check(payload, db_path)
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError("private directory must already exist")
    # Fixed hash filenames avoid user-supplied path traversal and are immutable.
    destination = directory / (report["sha256"] + ".json")
    blob = canonical(payload)
    try:
        fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        if destination.read_bytes() != blob:
            raise ValueError("snapshot hash collision")
        return report
    with os.fdopen(fd, "wb") as output:
        output.write(blob)
        output.flush()
        os.fsync(output.fileno())
    if destination.read_bytes() != blob:
        raise ValueError("snapshot readback mismatch")
    return report


def load(directory, sha):
    if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("invalid snapshot hash")
    raw = (Path(directory) / (sha + ".json")).read_bytes()
    payload = json.loads(raw)
    if digest(payload) != sha or canonical(payload) != raw:
        raise ValueError("snapshot integrity failure")
    return payload


def find(directory, deck_name=None, deck_id=None):
    if not deck_name and not deck_id:
        raise ValueError("deck name or id required")
    results = []
    for path in Path(directory).glob("*.json"):
        if len(path.stem) != 64:
            continue
        payload = load(directory, path.stem)
        if deck_id and payload["deck_id"] != deck_id:
            continue
        if deck_name and deck_name.casefold() not in payload["name"].casefold() and not any(
                deck_name.casefold() in a.casefold() for a in payload.get("aliases", [])):
            continue
        results.append({"sha256": path.stem, "deck_id": payload["deck_id"],
                        "name": payload["name"], "version": payload["version"],
                        "state": payload["state"], "summary": check(payload)})
    return sorted(results, key=lambda x: (x["deck_id"], x["version"], x["sha256"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["validate", "save", "find", "show"])
    parser.add_argument("--input")
    parser.add_argument("--private-dir")
    parser.add_argument("--db")
    parser.add_argument("--name")
    parser.add_argument("--deck-id")
    parser.add_argument("--sha256")
    a = parser.parse_args()
    if a.command in ("validate", "save"):
        if not a.input:
            parser.error("--input required")
        payload = json.loads(Path(a.input).read_text(encoding="utf-8"))
        result = check(payload, a.db) if a.command == "validate" else put(a.private_dir, payload, a.db)
    elif a.command == "find":
        result = find(a.private_dir, a.name, a.deck_id)
    else:
        result = load(a.private_dir, a.sha256)
        check(result, a.db)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
