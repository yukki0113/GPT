"""Five-race detail probe runner gated on an explicitly reviewed wire contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

from .capture import ALLOWED_HOST, CaptureRequest, execute_requests

APPROVED_RACE_KEYS = {
    "20160101|56|1",
    "20200101|53|1",
    "20250101|45|1",
    "20250109|26|1",
    "20250605|61|1",
}
ALLOWED_HEADERS = {"user-agent", "accept", "content-type", "referer", "origin"}


def load_sample_spec(path: Path, *, require_tokens: bool = True) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    samples = value.get("samples") if isinstance(value, dict) else None
    if not isinstance(samples, list) or len(samples) != 5:
        raise ValueError("sample spec must contain exactly five races")
    if any(not isinstance(sample, dict) for sample in samples):
        raise ValueError("each sample must be an object")
    keys = [sample.get("race_key") for sample in samples]
    if set(keys) != APPROVED_RACE_KEYS or len(set(keys)) != 5:
        raise ValueError("sample spec must contain exactly the five approved race keys")
    for sample in samples:
        token = sample.get("detail_token")
        if require_tokens and (not isinstance(token, str) or not token):
            raise ValueError(f"missing detail_token for {sample.get('race_key')}")
        if token is not None and (not isinstance(token, str) or not token):
            raise ValueError(f"invalid detail_token for {sample.get('race_key')}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(sample.get("source_raw_sha256", ""))):
            raise ValueError(f"invalid source_raw_sha256 for {sample.get('race_key')}")
    return samples


def load_reviewed_contract(path: Path) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(contract, dict) or contract.get("review_status") != "reviewed":
        raise ValueError("detail probe requires review_status='reviewed' contract")
    if not str(contract.get("reviewer", "")).strip() or not str(contract.get("reviewed_at", "")).strip():
        raise ValueError("reviewed contract must identify reviewer and reviewed_at")
    endpoint = contract.get("endpoint") or {}
    if endpoint != {"scheme": "https", "host": ALLOWED_HOST, "path": "/pc/racelive"}:
        raise ValueError("contract endpoint is fixed to https://keirin.jp/pc/racelive")
    method = str(contract.get("method", "")).upper()
    encoding = contract.get("encoding")
    if method not in {"GET", "POST"} or encoding not in {"query", "form"}:
        raise ValueError("contract must specify GET/POST and query/form encoding")
    if method == "GET" and encoding != "query":
        raise ValueError("GET contracts must use query encoding")
    token_field = contract.get("token_field")
    if not isinstance(token_field, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", token_field):
        raise ValueError("contract token_field is missing or malformed")
    mode_field = contract.get("mode_field")
    if mode_field is not None and (
        not isinstance(mode_field, str)
        or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", mode_field)
        or not isinstance(contract.get("mode_value"), str)
    ):
        raise ValueError("mode_field requires a valid mode_value")
    headers = contract.get("headers")
    if not isinstance(headers, dict):
        raise ValueError("contract headers must be an object")
    if any(str(name).lower() not in ALLOWED_HEADERS for name in headers):
        raise ValueError("only reviewed non-session headers are supported")
    if "cookie" in {str(name).lower() for name in headers}:
        raise ValueError("Cookie/session requests are not supported by this runner")
    source = contract.get("contract_source")
    if not isinstance(source, list) or not source:
        raise ValueError("contract_source must cite official JS or prior approved evidence")
    for item in source:
        if not isinstance(item, dict) or not item.get("file") or not item.get("observed_behavior"):
            raise ValueError("each contract_source entry needs file and observed_behavior")
    return contract


def build_detail_requests(
    samples: list[dict[str, Any]], contract: dict[str, Any]
) -> list[CaptureRequest]:
    if len(samples) != 5 or {sample.get("race_key") for sample in samples} != APPROVED_RACE_KEYS:
        raise ValueError("detail runner accepts only the exactly approved five races")
    endpoint = contract["endpoint"]
    base_url = urlunsplit((endpoint["scheme"], endpoint["host"], endpoint["path"], "", ""))
    headers = {str(k): str(v) for k, v in contract["headers"].items()}
    result = []
    for sample in samples:
        fields = {contract["token_field"]: sample["detail_token"]}
        if contract.get("mode_field") is not None:
            fields[contract["mode_field"]] = contract["mode_value"]
        body = b""
        url = base_url
        if contract["encoding"] == "query":
            url = base_url + "?" + urlencode(fields)
        else:
            body = urlencode(fields).encode("ascii")
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        result.append(
            CaptureRequest.build(
                method=contract["method"],
                url=url,
                headers=headers,
                body=body,
                source_evidence={
                    "race_key": sample["race_key"],
                    "source_raw_sha256": sample["source_raw_sha256"],
                    "contract_source": contract["contract_source"],
                },
            )
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare or run only the approved five-race detail probe")
    parser.add_argument("--sample-spec", type=Path, required=True)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--generation", required=True)
    parser.add_argument("--delay-seconds", type=float, default=3.0)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if args.execute and args.contract is None:
        parser.error("--execute requires a reviewed request-contract JSON")
    try:
        samples = load_sample_spec(args.sample_spec, require_tokens=args.contract is not None)
        if args.contract is None:
            result = {
                "status": "plan_blocked_contract_missing",
                "requests_sent": 0,
                "approved_race_keys": [sample["race_key"] for sample in samples],
                "detail": "No request contract was used or inferred.",
            }
        else:
            contract = load_reviewed_contract(args.contract)
            requests = build_detail_requests(samples, contract)
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
