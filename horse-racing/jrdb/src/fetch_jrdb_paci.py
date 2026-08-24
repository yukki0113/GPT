#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_jrdb_paci.py

JRDBの前日一括パック(PACI)を日付指定で取得する小さなCLIツールです。

設計方針:
- JRDB_USER / JRDB_PASSWORD を環境変数から取得
- HTTPSを優先し、HTTPへの自動フォールバックは行わない
- Basic認証
- 既存ZIPが正常なら再取得しない
- .part に保存してZIP検証後に確定ファイルへリネーム
- 401 / 403 / 404 / その他HTTPエラーを明確に区別
- ログを標準出力とファイルの両方へ出力可能

使用例:
  set JRDB_USER=xxxxxxxx
  set JRDB_PASSWORD=xxxxxxxx
  python fetch_jrdb_paci.py --date 20260815

PowerShell:
  $env:JRDB_USER="xxxxxxxx"
  $env:JRDB_PASSWORD="xxxxxxxx"
  python .\fetch_jrdb_paci.py --date 20260815

※ 認証情報をソースコードへ直書きしないでください。
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPBasicAuthHandler, HTTPPasswordMgrWithDefaultRealm, Request, build_opener

# www.jrdb.com は一部のHTTPS中継環境で証明書名不一致になるため、
# HTTPSで正常応答する非wwwホストを既定とする。
DEFAULT_BASE_URL = "https://jrdb.com/member/datazip/Paci"
ENV_USER = "JRDB_USER"
ENV_PASSWORD = "JRDB_PASSWORD"
SECRET_MODULE = "jrdb_secret"


class JrdbFetchError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="JRDB PACI ZIP downloader"
    )
    p.add_argument(
        "--date",
        required=True,
        help="対象日 YYYYMMDD 形式 (例: 20260815)",
    )
    p.add_argument(
        "--out-dir",
        default="downloads",
        help="保存先ディレクトリ (default: downloads)",
    )
    p.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"PACI配布ベースURL (default: {DEFAULT_BASE_URL})",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout seconds (default: 30)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="既存の正常ZIPがあっても再取得する",
    )
    p.add_argument(
        "--log-file",
        default=None,
        help="ログファイルパス。未指定なら out-dir/fetch_jrdb_paci_YYYYMMDD.log",
    )
    p.add_argument(
        "--show-url",
        action="store_true",
        help="生成した取得URLをログ表示する",
    )
    return p.parse_args()


def setup_logger(log_path: Path) -> logging.Logger:
    logger = logging.getLogger("jrdb_paci")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


def validate_date(date_str: str) -> datetime:
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
    except ValueError as e:
        raise JrdbFetchError(
            f"--date は YYYYMMDD 形式で指定してください: {date_str}"
        ) from e
    if dt.strftime("%Y%m%d") != date_str:
        raise JrdbFetchError(f"不正な日付です: {date_str}")
    return dt


def build_filename(dt: datetime) -> str:
    return f"PACI{dt.strftime('%y%m%d')}.zip"


def build_url(base_url: str, dt: datetime) -> str:
    year = dt.strftime("%Y")
    filename = build_filename(dt)
    return f"{base_url.rstrip('/')}/{year}/{filename}"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_valid_zip(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "file_not_found"
    if path.stat().st_size == 0:
        return False, "empty_file"

    try:
        if not zipfile.is_zipfile(path):
            return False, "not_zip"
        with zipfile.ZipFile(path, "r") as zf:
            bad = zf.testzip()
            if bad is not None:
                return False, f"corrupt_member:{bad}"
            names = zf.namelist()
            if not names:
                return False, "empty_archive"
        return True, "ok"
    except zipfile.BadZipFile:
        return False, "bad_zip"
    except Exception as e:
        return False, f"zip_check_error:{type(e).__name__}:{e}"


def load_credentials() -> tuple[str | None, str | None]:
    """Load credentials from environment variables, then from jrdb_secret.py.

    Values are intentionally never logged.  Import failures are handled by the
    caller without including exception details, because an exception can contain
    sensitive source text in unusual cases.
    """
    username = os.getenv(ENV_USER)
    password = os.getenv(ENV_PASSWORD)
    if username and password:
        return username, password
    try:
        secret = __import__(SECRET_MODULE)
        username = username or getattr(secret, ENV_USER, None)
        password = password or getattr(secret, ENV_PASSWORD, None)
    except Exception:
        return None, None
    return username, password


def response_preview(body: bytes, content_type: str, limit: int = 200) -> str:
    ctype = content_type
    if "text" not in ctype.lower() and "html" not in ctype.lower():
        return ""
    try:
        text = body[:limit].decode("utf-8", errors="replace")
        return " ".join(text[:limit].split())
    except Exception:
        return ""


def log_response_metadata(
    logger: logging.Logger,
    status: int,
    final_url: str,
    content_type: str | None,
    content_length: str | None,
) -> None:
    logger.info(
        "HTTP status=%s Content-Type=%s Content-Length=%s Final-URL=%s",
        status,
        content_type or "",
        content_length or "",
        final_url,
    )


def fetch(
    url: str,
    dest: Path,
    username: str,
    password: str,
    timeout: int,
    logger: logging.Logger,
) -> None:
    part = dest.with_suffix(dest.suffix + ".part")
    if part.exists():
        part.unlink()

    logger.info("HTTP GET 開始")
    password_mgr = HTTPPasswordMgrWithDefaultRealm()
    password_mgr.add_password(None, url, username, password)
    opener = build_opener(HTTPBasicAuthHandler(password_mgr))
    request = Request(url, headers={"User-Agent": "RaceNote-JRDB-PACI/0.2"})

    try:
        with opener.open(request, timeout=timeout) as response:
            status = response.status
            ctype = response.headers.get("Content-Type")
            clen = response.headers.get("Content-Length")
            log_response_metadata(logger, status, response.geturl(), ctype, clen)
            if status != 200:
                raise JrdbFetchError(f"HTTP {status}: 取得に失敗しました。")
            with part.open("wb") as f:
                while chunk := response.read(1024 * 256):
                    f.write(chunk)
    except HTTPError as e:
        part.unlink(missing_ok=True)
        body = e.read(400)
        log_response_metadata(
            logger, e.code, e.geturl(), e.headers.get("Content-Type"), e.headers.get("Content-Length")
        )
        if e.code == 401:
            raise JrdbFetchError(
                "401 Unauthorized: JRDB_USER / JRDB_PASSWORD または認証方式を確認してください。"
            ) from e
        if e.code == 403:
            raise JrdbFetchError(
                "403 Forbidden: JRDB側のアクセス制限・権限・URLを確認してください。"
            ) from e
        if e.code == 404:
            raise JrdbFetchError(
                "404 Not Found: 指定日のPACIが未提供、またはURL規則が異なる可能性があります。"
            ) from e
        preview = response_preview(body, e.headers.get("Content-Type", ""))
        extra = f" body={preview!r}" if preview else ""
        raise JrdbFetchError(f"HTTP {e.code}: 取得に失敗しました。{extra}") from e
    except URLError as e:
        part.unlink(missing_ok=True)
        raise JrdbFetchError(f"通信エラー: {e.reason}") from e
    except TimeoutError as e:
        part.unlink(missing_ok=True)
        raise JrdbFetchError("通信エラー: timeout") from e
    except Exception:
        part.unlink(missing_ok=True)
        raise

    ok, reason = is_valid_zip(part)
    if not ok:
        try:
            preview = ""
            raw = part.read_bytes()[:400]
            preview = raw.decode("cp932", errors="replace")
            preview = " ".join(preview.split())
        except Exception:
            preview = ""
        part.unlink(missing_ok=True)
        suffix = f" preview={preview[:200]!r}" if preview else ""
        raise JrdbFetchError(
            f"HTTP 200 でしたが有効なZIPではありません: {reason}.{suffix}"
        )

    part.replace(dest)


def summarize_zip(path: Path) -> tuple[int, list[str]]:
    with zipfile.ZipFile(path, "r") as zf:
        names = zf.namelist()
    return len(names), names


def main() -> int:
    args = parse_args()

    try:
        dt = validate_date(args.date)
        out_dir = Path(args.out_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        log_path = (
            Path(args.log_file).resolve()
            if args.log_file
            else out_dir / f"fetch_jrdb_paci_{args.date}.log"
        )
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logger = setup_logger(log_path)

        username, password = load_credentials()

        if not username or not password:
            raise JrdbFetchError(
                f"{ENV_USER} / {ENV_PASSWORD} または {SECRET_MODULE}.py を設定してください。"
            )

        filename = build_filename(dt)
        dest = out_dir / filename
        url = build_url(args.base_url, dt)

        logger.info("対象日=%s", args.date)
        logger.info("出力先=%s", dest)
        logger.info("Base URL=%s", args.base_url)
        if args.show_url:
            logger.info("取得URL=%s", url)

        if dest.exists() and not args.force:
            ok, reason = is_valid_zip(dest)
            if ok:
                count, names = summarize_zip(dest)
                logger.info(
                    "既存ファイルが正常ZIPのため取得をスキップ: size=%d sha256=%s members=%d",
                    dest.stat().st_size,
                    sha256_file(dest),
                    count,
                )
                logger.info("ZIP members: %s", ", ".join(names))
                print(str(dest))
                return 0
            logger.warning(
                "既存ファイルが不正なため再取得します: reason=%s", reason
            )

        fetch(
            url=url,
            dest=dest,
            username=username,
            password=password,
            timeout=args.timeout,
            logger=logger,
        )

        count, names = summarize_zip(dest)
        logger.info(
            "取得成功: size=%d sha256=%s members=%d",
            dest.stat().st_size,
            sha256_file(dest),
            count,
        )
        logger.info("ZIP members: %s", ", ".join(names))
        print(str(dest))
        return 0

    except JrdbFetchError as e:
        try:
            logger.error("%s", e)  # type: ignore[name-defined]
        except Exception:
            print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        try:
            logger.exception("予期しないエラー: %s", e)  # type: ignore[name-defined]
        except Exception:
            print(f"ERROR: 予期しないエラー: {e}", file=sys.stderr)
        return 99


if __name__ == "__main__":
    raise SystemExit(main())
