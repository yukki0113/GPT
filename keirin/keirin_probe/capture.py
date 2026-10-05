"""Sequential immutable HTTP capture primitives; never follows redirects or retries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import tempfile
import time
from typing import Any, Callable, Iterable
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)

ALLOWED_HOST = "keirin.jp"
MIN_DELAY_SECONDS = 3.0
RESTRICTION_TEXT = re.compile(
    r"アクセス.{0,12}(?:制限|集中|拒否)|利用.{0,8}制限|"
    r"access denied|access restricted|too many requests|rate.?limit|forbidden",
    re.IGNORECASE,
)


class CaptureError(RuntimeError):
    """Raised when a capture must fail closed."""


class CachedRequestError(CaptureError):
    """Raised when a request identity has already been attempted."""


class NoRedirectHandler(HTTPRedirectHandler):
    """Expose redirect response to caller instead of issuing a second request."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


@dataclass(frozen=True)
class CaptureRequest:
    request_id: str
    method: str
    url: str
    headers: tuple[tuple[str, str], ...]
    body: bytes
    source_evidence: dict[str, Any]

    @classmethod
    def build(
        cls,
        *,
        method: str,
        url: str,
        headers: dict[str, str] | Iterable[tuple[str, str]],
        body: bytes = b"",
        source_evidence: dict[str, Any] | None = None,
    ) -> "CaptureRequest":
        method = method.upper()
        if method not in {"GET", "POST"}:
            raise ValueError("only GET/POST are supported")
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST:
            raise ValueError(f"request host must be https://{ALLOWED_HOST}")
        if parsed.username or parsed.password or parsed.port or parsed.fragment:
            raise ValueError("credentials, explicit ports, and URL fragments are forbidden")
        pairs = tuple(headers.items()) if isinstance(headers, dict) else tuple(headers)
        normalized = tuple((str(k), str(v)) for k, v in pairs)
        if any(k.lower() in {"cookie", "authorization", "proxy-authorization"} for k, _ in normalized):
            raise ValueError("Cookie and authorization headers are not supported")
        canonical = json.dumps(
            {
                "method": method,
                "url": url,
                "headers": sorted((k.lower(), v) for k, v in normalized),
                "body_sha256": sha256(body).hexdigest(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return cls(
            request_id=sha256(canonical).hexdigest(),
            method=method,
            url=url,
            headers=normalized,
            body=body,
            source_evidence=source_evidence or {},
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise


def _write_new(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _header_pairs(headers: Any) -> list[list[str]]:
    if headers is None:
        return []
    # email.message.Message.items() retains observable order and duplicate fields.
    return [[str(k), str(v)] for k, v in headers.items()]


def _read_http_error(exc: HTTPError) -> tuple[int, Any, bytes, str]:
    body = exc.read()
    return int(exc.code), exc.headers, body, exc.geturl()


def execute_requests(
    requests: Iterable[CaptureRequest],
    *,
    generation_dir: Path,
    cache_index: Path,
    execute: bool = False,
    delay_seconds: float = MIN_DELAY_SECONDS,
    opener: Callable[..., Any] | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Plan or capture a small sequential request set.

    A pending cache entry is persisted before each network call. If the process
    dies mid-request, the request is not retried automatically on the next run.
    """
    items = list(requests)
    if not items:
        raise ValueError("request set cannot be empty")
    if len(items) > 5:
        raise ValueError("maximum request count is five")
    if delay_seconds < MIN_DELAY_SECONDS:
        raise ValueError("delay_seconds must be >= 3.0")
    if len({item.request_id for item in items}) != len(items):
        raise ValueError("duplicate request identity in request set")
    for item in items:
        parsed = urlsplit(item.url)
        if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST:
            raise ValueError("all requests must target https://keirin.jp")

    plan = {
        "status": "plan_only",
        "requests_sent": 0,
        "requests": [
            {
                "request_id": item.request_id,
                "method": item.method,
                "url": item.url,
                "headers": [list(pair) for pair in item.headers],
                "body_length": len(item.body),
                "body_sha256": sha256(item.body).hexdigest(),
                "source_evidence": item.source_evidence,
            }
            for item in items
        ],
    }
    if not execute:
        return plan

    cache_index.parent.mkdir(parents=True, exist_ok=True)
    if cache_index.exists():
        cache = json.loads(cache_index.read_text(encoding="utf-8"))
        if not isinstance(cache, dict):
            raise ValueError("cache index must be a JSON object")
    else:
        cache = {}
    prior = [item.request_id for item in items if item.request_id in cache]
    if prior:
        raise CachedRequestError(f"request identities already attempted: {prior}")
    if generation_dir.exists():
        raise FileExistsError(f"capture generation already exists: {generation_dir}")
    generation_dir.mkdir(parents=True)

    manifest: dict[str, Any] = {
        "status": "running",
        "requests_planned": len(items),
        "requests_sent": 0,
        "captured_at_utc": _utc_now(),
        "generation_dir": str(generation_dir),
        "records": [],
    }
    manifest_path = generation_dir / "manifest.json"
    _atomic_json(manifest_path, manifest)
    network = opener or build_opener(NoRedirectHandler()).open
    last_started: float | None = None

    for index, item in enumerate(items):
        if last_started is not None:
            gap = clock() - last_started
            if gap < delay_seconds:
                sleep(delay_seconds - gap)

        started_at = _utc_now()
        started_tick = clock()
        last_started = started_tick
        suffix = item.request_id[:16]
        body_rel = f"responses/{index + 1:02d}_{suffix}.body"
        headers_rel = f"responses/{index + 1:02d}_{suffix}.headers.json"
        request_body_rel = None
        if item.body:
            request_body_rel = f"requests/{index + 1:02d}_{suffix}.body"
            _write_new(generation_dir / request_body_rel, item.body)
        record = {
            "request_id": item.request_id,
            "method": item.method,
            "requested_url": item.url,
            "request_headers": [list(pair) for pair in item.headers],
            "request_body_file": request_body_rel,
            "request_body_bytes": len(item.body),
            "request_body_sha256": sha256(item.body).hexdigest(),
            "started_at_utc": started_at,
            "elapsed_seconds": None,
            "http_status": None,
            "redirect_location": None,
            "final_url": None,
            "response_headers_file": None,
            "response_headers": [],
            "response_body_file": None,
            "response_bytes": None,
            "response_sha256": None,
            "source_evidence": item.source_evidence,
            "transport_error": None,
            "restriction_text_detected": False,
            "capture_status": "request_started",
        }
        manifest["records"].append(record)
        cache[item.request_id] = {
            "status": "sent_pending_capture",
            "generation_dir": str(generation_dir),
            "started_at_utc": started_at,
        }
        _atomic_json(cache_index, cache)
        _atomic_json(manifest_path, manifest)

        request = Request(
            item.url,
            data=item.body if item.method == "POST" else None,
            headers=dict(item.headers),
            method=item.method,
        )
        status: int | None = None
        response_headers: Any = None
        response_body = b""
        final_url: str | None = None
        transport_error: str | None = None
        try:
            with network(request, timeout=30) as response:
                status = int(getattr(response, "status", response.getcode()))
                response_headers = response.headers
                response_body = response.read()
                final_url = response.geturl()
        except HTTPError as exc:
            status, response_headers, response_body, final_url = _read_http_error(exc)
        except Exception as exc:  # one attempt only; record and stop
            transport_error = f"{type(exc).__name__}: {exc}"

        elapsed = max(0.0, clock() - started_tick)
        if status is not None:
            _write_new(generation_dir / body_rel, response_body)
            header_data = _header_pairs(response_headers)
            _write_new(
                generation_dir / headers_rel,
                (json.dumps(header_data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            )
        else:
            body_rel = headers_rel = None
            header_data = []

        lower_headers = {key.lower(): value for key, value in header_data}
        location = lower_headers.get("location")
        text = response_body.decode("utf-8", errors="replace") if response_body else ""
        restricted_text = bool(RESTRICTION_TEXT.search(text))
        redirect = status is not None and 300 <= status < 400
        blocked = status in {403, 429} or redirect or restricted_text or transport_error is not None
        if status is not None and not 200 <= status < 300:
            blocked = True

        record.update(
            {
                "elapsed_seconds": elapsed,
                "http_status": status,
                "redirect_location": location,
                "final_url": final_url,
                "response_headers_file": headers_rel,
                "response_headers": header_data,
                "response_body_file": body_rel,
                "response_bytes": len(response_body) if status is not None else None,
                "response_sha256": sha256(response_body).hexdigest() if status is not None else None,
                "transport_error": transport_error,
                "restriction_text_detected": restricted_text,
                "capture_status": "captured" if status is not None else "transport_error",
            }
        )
        manifest["requests_sent"] += 1
        cache[item.request_id].update(
            {
                "status": "captured" if status is not None else "transport_error",
                "http_status": status,
                "response_sha256": record["response_sha256"],
                "generation_dir": str(generation_dir),
            }
        )
        manifest["status"] = "stopped" if blocked else "running"
        if blocked:
            manifest["stop_reason"] = (
                "access restriction or transport stop"
                if status in {403, 429} or restricted_text
                else "redirect requires manual review"
                if redirect
                else "non-success HTTP status"
                if status is not None and not 200 <= status < 300
                else transport_error
            )
        _atomic_json(cache_index, cache)
        _atomic_json(manifest_path, manifest)
        if blocked:
            return manifest

    manifest["status"] = "complete"
    _atomic_json(manifest_path, manifest)
    return manifest
