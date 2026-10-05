"""Allowlisted capture of official JS assets referenced by immutable Historical Raw."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

from .capture import ALLOWED_HOST, CaptureRequest, execute_requests

DEFAULT_ASSET_PATHS = {
    "/pc/static/js/commonSubmit.js",
    "/pc/static/js/PJ0301_c.js",
    "/pc/static/js/FPJ0305.js",
}
USER_AGENT = "Mozilla/5.0 (compatible; keirin-historical-probe/0.1)"


def load_evidence(path: Path) -> dict[str, Any]:
    evidence = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(evidence, dict) or not isinstance(evidence.get("assets"), list):
        raise ValueError("evidence file must contain an assets array")
    seen: set[str] = set()
    for item in evidence["assets"]:
        asset_path = item.get("path")
        if asset_path not in DEFAULT_ASSET_PATHS:
            raise ValueError(f"asset path is not allowlisted: {asset_path!r}")
        if asset_path in seen:
            raise ValueError(f"duplicate asset evidence: {asset_path}")
        seen.add(asset_path)
        references = item.get("references")
        if not isinstance(references, list) or not references:
            raise ValueError(f"asset {asset_path} has no Raw references")
        for reference in references:
            digest = reference.get("raw_sha256", "")
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError(f"invalid source Raw SHA for {asset_path}")
            if asset_path not in reference.get("script_src_values", []):
                raise ValueError(f"Raw evidence does not contain exact script path {asset_path}")
    if seen != DEFAULT_ASSET_PATHS:
        raise ValueError(f"evidence must cover the fixed asset allowlist: {sorted(DEFAULT_ASSET_PATHS)}")
    return evidence


def build_requests(evidence: dict[str, Any]) -> list[CaptureRequest]:
    items = []
    for asset in evidence["assets"]:
        path = asset["path"]
        items.append(
            CaptureRequest.build(
                method="GET",
                url=f"https://{ALLOWED_HOST}{path}",
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/javascript,text/javascript,*/*;q=0.5",
                },
                source_evidence={
                    "purpose": asset["purpose"],
                    "references": asset["references"],
                },
            )
        )
    return items


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture only the approved KEIRIN.JP JS asset set")
    parser.add_argument("--evidence-file", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--generation", required=True)
    parser.add_argument("--delay-seconds", type=float, default=3.0)
    parser.add_argument("--execute", action="store_true", help="send the explicitly allowlisted GETs")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", args.generation):
        parser.error("generation must use 1-80 ASCII letters, digits, dot, underscore, or hyphen")
    try:
        evidence = load_evidence(args.evidence_file)
        requests = build_requests(evidence)
        result = execute_requests(
            requests,
            generation_dir=args.output_root / args.generation,
            cache_index=args.output_root / "request-cache.json",
            execute=args.execute,
            delay_seconds=args.delay_seconds,
        )
    except (ValueError, OSError, RuntimeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
