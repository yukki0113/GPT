"""Offline evidence extractor for locally captured JavaScript; never performs I/O."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

SEARCH_TERMS = (
    "/pc/racelive",
    "strLnkPrm",
    "strLnkKBn",
    "hhhdnPostUrl1",
    "slRaceBasicInfoURL",
    "encp",
    "disp",
    "form",
    "submit",
    "createElement",
    "setAttribute",
    "appendChild",
    "type=hidden",
    "hidden",
    "URLSearchParams",
    "encodeURIComponent",
    "serialize",
    "serializeArray",
    "XMLHttpRequest.open",
    "$.post",
    "jQuery.post",
    "method:",
    "type:",
    "data:",
    "POST",
    "GET",
    "window.location",
    "location.href",
    "fetch",
    "XMLHttpRequest",
    "$.ajax",
    "jQuery.ajax",
    "Content-Type",
    "Referer",
    "Origin",
    "raceNo",
    "ChgRace",
    "RaceNo",
)
SYMBOL_PATTERNS = (
    re.compile(r"function\s+([\w$]+)\s*\(", re.I),
    re.compile(r"(?:var|let|const)\s+([\w$]+)\s*=\s*function\b", re.I),
    re.compile(r"(?:var|let|const)\s+([\w$]+)\s*=\s*(?:\([^)]*\)|[\w$]+)\s*=>", re.I),
)


def _nearest_symbol(text: str, offset: int) -> str | None:
    prefix = text[:offset]
    last: tuple[int, str] | None = None
    for pattern in SYMBOL_PATTERNS:
        for match in pattern.finditer(prefix):
            if last is None or match.start() > last[0]:
                last = (match.start(), match.group(1))
    return last[1] if last else None


def analyze_generation(generation_dir: Path) -> dict[str, Any]:
    manifest_path = generation_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") not in {"complete", "stopped"}:
        raise ValueError("capture manifest is not finalized")
    evidence: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    for record in manifest.get("records", []):
        if record.get("http_status") != 200:
            continue
        body_rel = record.get("response_body_file")
        if not body_rel:
            continue
        body_path = generation_dir / body_rel
        body = body_path.read_bytes()
        digest = sha256(body).hexdigest()
        if digest != record.get("response_sha256"):
            raise ValueError(f"captured asset hash mismatch: {body_rel}")
        text = body.decode("utf-8", errors="replace")
        files.append(
            {
                "path": body_rel,
                "requested_url": record["requested_url"],
                "bytes": len(body),
                "sha256": digest,
            }
        )
        lower = text.lower()
        for term in SEARCH_TERMS:
            needle = term.lower()
            cursor = 0
            while True:
                index = lower.find(needle, cursor)
                if index < 0:
                    break
                start = max(0, index - 240)
                end = min(len(text), index + len(term) + 280)
                line = text.count("\n", 0, index) + 1
                evidence.append(
                    {
                        "file": body_rel,
                        "requested_url": record["requested_url"],
                        "term": term,
                        "symbol": _nearest_symbol(text, index),
                        "line": line,
                        "byte_start": len(text[:index].encode("utf-8")),
                        "byte_end": len(text[: index + len(term)].encode("utf-8")),
                        "observed_text": text[index : index + len(term)],
                        "context": text[start:end],
                        "observed_behavior": "literal/source-text occurrence only; no request semantics inferred",
                        "confidence": "Unknown",
                    }
                )
                cursor = index + max(1, len(needle))
    return {
        "analysis_version": "0.1",
        "capture_generation": str(generation_dir),
        "captured_files": files,
        "evidence_count": len(evidence),
        "evidence": evidence,
        "conclusions": [],
        "interpretation_policy": "Do not infer wire parameters from names alone. Manually cite code that constructs the request before upgrading confidence.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze captured KEIRIN.JP scripts offline")
    parser.add_argument("--capture-generation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = analyze_generation(args.capture_generation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"status": "success", "evidence_count": result["evidence_count"], "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
