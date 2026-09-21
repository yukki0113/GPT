"""Source-agnostic immutable raw acquisition for keirin historical data."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import time
from typing import Any, Callable, Iterable
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

USER_AGENT = "Mozilla/5.0 (compatible; keirin-historical-research/0.1)"
APPROVED_POLICY_STATUSES = {"approved", "personal_research_approved"}


class PolicyNotApprovedError(RuntimeError):
    """Raised when a source has not been approved for automated acquisition."""


class RawAcquisitionError(RuntimeError):
    """Raised when transport or raw validation fails."""


@dataclass(frozen=True)
class SourceItem:
    provider: str
    source_id: str
    url: str
    relative_path: str
    policy_status: str
    request_method: str = "GET"
    form_data: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "SourceItem":
        required = ("provider", "source_id", "url", "relative_path", "policy_status")
        missing = [key for key in required if not value.get(key)]
        if missing:
            raise ValueError(f"missing required source fields: {', '.join(missing)}")
        metadata = value.get("metadata") or {}
        form_data = value.get("form_data") or {}
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be an object")
        if not isinstance(form_data, dict):
            raise ValueError("form_data must be an object")
        item = cls(
            provider=str(value["provider"]),
            source_id=str(value["source_id"]),
            url=str(value["url"]),
            relative_path=str(value["relative_path"]),
            policy_status=str(value["policy_status"]),
            request_method=str(value.get("request_method") or "GET").upper(),
            form_data={str(k): str(v) for k, v in form_data.items()},
            metadata=metadata,
        )
        item.validate()
        return item

    def validate(self) -> None:
        parsed = urlparse(self.url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError(f"source URL must be absolute https: {self.url}")
        path = PurePosixPath(self.relative_path)
        if path.is_absolute() or ".." in path.parts or not path.name:
            raise ValueError(f"relative_path must stay inside output root: {self.relative_path}")
        if self.request_method not in {"GET", "POST"}:
            raise ValueError("request_method must be GET or POST")
        if self.request_method == "GET" and self.form_data:
            raise ValueError("GET source must not include form_data")
        if self.request_method == "POST" and not self.form_data:
            raise ValueError("POST source requires form_data")


@dataclass(frozen=True)
class HttpResponse:
    content: bytes
    status_code: int
    content_type: str
    final_url: str


def fetch_source(
    item: SourceItem,
    *,
    timeout: float = 60.0,
    opener: Callable[..., object] = urlopen,
) -> HttpResponse:
    if item.policy_status not in APPROVED_POLICY_STATUSES:
        raise PolicyNotApprovedError(
            f"provider {item.provider!r} is not approved for automated acquisition "
            f"(policy_status={item.policy_status!r})"
        )

    data = None
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/json,text/csv,*/*;q=0.5",
    }
    if item.request_method == "POST":
        data = urlencode(item.form_data).encode("ascii")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    referer = item.metadata.get("referer")
    if referer:
        headers["Referer"] = str(referer)

    request = Request(item.url, data=data, headers=headers, method=item.request_method)
    try:
        with opener(request, timeout=timeout) as response:
            status = int(getattr(response, "status", response.getcode()))
            content = response.read()
            content_type = response.headers.get("Content-Type", "")
            final_url = response.geturl()
    except Exception as exc:
        raise RawAcquisitionError(f"fetch failed for {item.source_id}: {exc}") from exc
    if status != 200:
        raise RawAcquisitionError(f"HTTP {status} for {item.source_id}")
    if not content:
        raise RawAcquisitionError(f"empty response for {item.source_id}")
    return HttpResponse(content, status, content_type, final_url)


def write_immutable(path: Path, content: bytes) -> str:
    digest = sha256(content).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        current = sha256(path.read_bytes()).hexdigest()
        if current == digest:
            return "unchanged"
        raise FileExistsError(f"refusing to overwrite immutable raw file with different bytes: {path}")
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        temp_path = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return "downloaded"


def load_source_list(path: Path) -> list[SourceItem]:
    items: list[SourceItem] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw_line in enumerate(handle, 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at line {line_no}: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"source list line {line_no} must be a JSON object")
            items.append(SourceItem.from_mapping(value))
    if not items:
        raise ValueError("source list is empty")
    return items


def acquire_source_list(
    sources: Iterable[SourceItem],
    *,
    output_dir: Path,
    manifest_path: Path,
    delay_seconds: float = 1.0,
    timeout: float = 60.0,
    opener: Callable[..., object] = urlopen,
    continue_on_error: bool = True,
) -> dict[str, Any]:
    if delay_seconds < 0:
        raise ValueError("delay_seconds must be >= 0")
    source_items = list(sources)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    success_count = failure_count = policy_blocked_count = 0
    total_bytes = 0

    for index, item in enumerate(source_items):
        record: dict[str, Any] = asdict(item)
        record["started_at_utc"] = datetime.now(timezone.utc).isoformat()
        try:
            response = fetch_source(item, timeout=timeout, opener=opener)
            target = output_dir / Path(item.relative_path)
            write_status = write_immutable(target, response.content)
            record.update(
                {
                    "status": "success",
                    "write_status": write_status,
                    "http_status": response.status_code,
                    "content_type": response.content_type,
                    "final_url": response.final_url,
                    "size_bytes": len(response.content),
                    "sha256": sha256(response.content).hexdigest(),
                    "saved_path": str(target),
                }
            )
            success_count += 1
            total_bytes += len(response.content)
        except PolicyNotApprovedError as exc:
            policy_blocked_count += 1
            failure_count += 1
            record.update({"status": "policy_blocked", "error": str(exc)})
            if not continue_on_error:
                records.append(record)
                break
        except Exception as exc:
            failure_count += 1
            record.update({"status": "failure", "error": f"{type(exc).__name__}: {exc}"})
            if not continue_on_error:
                records.append(record)
                break
        records.append(record)
        if index + 1 < len(source_items) and delay_seconds:
            time.sleep(delay_seconds)

    status = "success" if failure_count == 0 else "partial_failure"
    if success_count == 0 and failure_count:
        status = "failure"
    manifest: dict[str, Any] = {
        "status": status,
        "requested_sources": len(source_items),
        "successful_sources": success_count,
        "failed_sources": failure_count,
        "policy_blocked_sources": policy_blocked_count,
        "total_bytes": total_bytes,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": records,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Acquire approved keirin historical raw sources")
    parser.add_argument("--source-list", type=Path, required=True, help="JSONL source manifest")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest-path", type=Path, required=True)
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--fail-fast", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    manifest = acquire_source_list(
        load_source_list(args.source_list),
        output_dir=args.output_dir,
        manifest_path=args.manifest_path,
        delay_seconds=args.delay_seconds,
        timeout=args.timeout,
        continue_on_error=not args.fail_fast,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest["failed_sources"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
