#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
master_eval_media_collector.py

@master_eval の対象Tweet/Post IDから添付画像を取得するためのテスト用コレクタ。
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0 Safari/537.36"
)

class FetchError(RuntimeError):
    pass

class HttpResponse:
    def __init__(self, status_code: int, headers: Any, content: bytes) -> None:
        self.status_code = status_code
        self.headers = headers
        self.content = content

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise FetchError(f"HTTP {self.status_code}")

    def json(self) -> Dict[str, Any]:
        return json.loads(self.content.decode("utf-8"))

class HttpSession:
    def __init__(self) -> None:
        self.headers = {"User-Agent": UA, "Accept": "*/*"}
        self._opener = build_opener()

    def get(self, url: str, timeout: int) -> HttpResponse:
        request = Request(url, headers=self.headers)
        try:
            with self._opener.open(request, timeout=timeout) as response:
                return HttpResponse(response.status, response.headers, response.read())
        except HTTPError as e:
            return HttpResponse(e.code, e.headers, e.read())
        except URLError as e:
            raise FetchError(f"HTTP接続に失敗しました: {e.reason}") from e

def _session() -> HttpSession:
    return HttpSession()

def _get_json(session: HttpSession, url: str, timeout: int = 20) -> Dict[str, Any]:
    r = session.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()

def fetch_via_fxtwitter(session: HttpSession, tweet_id: str) -> Optional[Dict[str, Any]]:
    candidates = [
        f"https://api.fxtwitter.com/status/{tweet_id}",
        f"https://api.fxtwitter.com/Twitter/status/{tweet_id}",
    ]
    for url in candidates:
        try:
            data = _get_json(session, url)
            if data:
                return {"source": "fxtwitter", "endpoint": url, "raw": data}
        except Exception:
            continue
    return None

def fetch_via_syndication(session: HttpSession, tweet_id: str) -> Optional[Dict[str, Any]]:
    url = f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&lang=ja"
    try:
        data = _get_json(session, url)
        if data:
            return {"source": "syndication", "endpoint": url, "raw": data}
    except Exception:
        return None
    return None

def _walk(obj: Any) -> Iterable[Any]:
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)

def extract_image_urls(payload: Dict[str, Any]) -> List[str]:
    found: List[str] = []

    def add(url: str) -> None:
        if not isinstance(url, str):
            return
        if "pbs.twimg.com/media/" in url:
            if "?" in url:
                base = url.split("?", 1)[0]
                ext = _guess_ext_from_url(url)
                if ext:
                    url = f"{base}?format={ext.lstrip('.')}&name=orig"
                else:
                    url = f"{base}?name=orig"
            elif ":large" in url:
                url = url.replace(":large", ":orig")
            found.append(url)

    for node in _walk(payload):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            if isinstance(value, str):
                add(value)
            elif key.lower() in {
                "url", "media_url", "media_url_https", "image_url",
                "thumbnail_url", "original_url"
            } and isinstance(value, str):
                add(value)

    return list(dict.fromkeys(found))

def _guess_ext_from_url(url: str) -> Optional[str]:
    m = re.search(r"[?&]format=([a-zA-Z0-9]+)", url)
    if m:
        return "." + m.group(1).lower()

    path = urlparse(url).path
    suffix = Path(path).suffix
    if suffix and len(suffix) <= 6:
        return suffix.lower()
    return None

def download_image(session: HttpSession, url: str, dest_base: Path) -> Path:
    r = session.get(url, timeout=30)
    r.raise_for_status()

    ctype = (r.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    ext = mimetypes.guess_extension(ctype) if ctype.startswith("image/") else None
    if ext == ".jpe":
        ext = ".jpg"
    if not ext:
        ext = _guess_ext_from_url(url) or ".jpg"

    dest = dest_base.with_suffix(ext)
    dest.write_bytes(r.content)
    return dest

def fetch_tweet_payload(session: HttpSession, tweet_id: str) -> Dict[str, Any]:
    for fn in (fetch_via_fxtwitter, fetch_via_syndication):
        result = fn(session, tweet_id)
        if result:
            return result
    raise FetchError(f"Tweet {tweet_id}: public JSON endpoints から取得できませんでした。")

def collect(tweet_ids: List[str], out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    session = _session()
    failures = 0

    for tweet_id in tweet_ids:
        print(f"[INFO] Tweet {tweet_id}")
        tdir = out_dir / tweet_id
        tdir.mkdir(parents=True, exist_ok=True)

        try:
            payload = fetch_tweet_payload(session, tweet_id)
        except Exception as e:
            failures += 1
            print(f"[ERROR] metadata: {e}")
            continue

        (tdir / "metadata.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        urls = extract_image_urls(payload)
        print(f"[INFO] image candidates: {len(urls)}")

        if not urls:
            failures += 1
            print("[WARN] 添付画像URLを検出できませんでした。")
            continue

        for i, url in enumerate(urls, 1):
            try:
                path = download_image(session, url, tdir / f"media_{i:02d}")
                print(f"[OK] {path.name}")
            except Exception as e:
                failures += 1
                print(f"[ERROR] media_{i:02d}: {e}")

    return failures

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("tweet_ids", nargs="+", help="X/Twitter status ID（複数可）")
    p.add_argument("--out", default="master_eval_media", help="出力ディレクトリ")
    return p.parse_args()

def main() -> int:
    args = parse_args()
    failures = collect(args.tweet_ids, Path(args.out))
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
