from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from keirin_historical.keirin_jp_month import discover_events
from keirin_historical.raw import SourceItem, acquire_source_list, load_source_list, write_immutable


class FakeResponse:
    def __init__(self, body: bytes, *, url: str = "https://approved.example/race/1") -> None:
        self.status = 200
        self._body = body
        self._url = url
        self.headers = {"Content-Type": "text/html; charset=utf-8"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._body

    def geturl(self) -> str:
        return self._url

    def getcode(self) -> int:
        return self.status


def fake_opener(request, timeout=0):
    if request.method == "POST":
        assert request.data == b"encp=abc&disp=PJ0301"
    return FakeResponse(b"<html>fixture</html>", url=request.full_url)


class RawCollectorTests(unittest.TestCase):
    def test_policy_gate_blocks_unapproved_source(self) -> None:
        source = SourceItem("example", "r1", "https://example.test/1", "2016/01/r1.html", "review_pending")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = acquire_source_list(
                [source], output_dir=root / "raw", manifest_path=root / "manifest.json",
                delay_seconds=0, opener=fake_opener,
            )
            self.assertEqual(manifest["policy_blocked_sources"], 1)
            self.assertEqual(manifest["successful_sources"], 0)

    def test_personal_research_post_source_is_saved(self) -> None:
        source = SourceItem(
            "keirin.jp", "r1", "https://approved.example/race/1", "2016/01/r1.html",
            "personal_research_approved", request_method="POST",
            form_data={"encp": "abc", "disp": "PJ0301"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = acquire_source_list(
                [source], output_dir=root / "raw", manifest_path=root / "manifest.json",
                delay_seconds=0, opener=fake_opener,
            )
            self.assertEqual(manifest["successful_sources"], 1)
            self.assertEqual((root / "raw/2016/01/r1.html").read_bytes(), b"<html>fixture</html>")

    def test_raw_is_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw.html"
            self.assertEqual(write_immutable(path, b"same"), "downloaded")
            self.assertEqual(write_immutable(path, b"same"), "unchanged")
            with self.assertRaises(FileExistsError):
                write_immutable(path, b"different")

    def test_source_list_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.jsonl"
            path.write_text(json.dumps({
                "provider": "x", "source_id": "x", "url": "https://example.test/x",
                "relative_path": "2016/01/x.html", "policy_status": "approved",
            }) + "\n", encoding="utf-8")
            items = load_source_list(path)
            self.assertEqual(items[0].source_id, "x")

    def test_reject_path_escape(self) -> None:
        with self.assertRaises(ValueError):
            SourceItem.from_mapping({
                "provider": "x", "source_id": "x", "url": "https://example.test/x",
                "relative_path": "../escape", "policy_status": "approved",
            })

    def test_discover_events_from_schedule_rows(self) -> None:
        schedule = """
        <tr class="tr_h">
          <td class="td_keirinjo"><a href="/pc/jyosellinfo?jocd=13">いわき平</a></td>
          <td class="td_day bk_kaisai clc" colspan="3">
            <a href="javascript:void(0);" data-pprm-href="/pc/racelist"
               data-pprm-encp="token1" data-pprm-dkbn="1">
              <img src="/pc/static/img/icon/grade/ico_f1.png" />
            </a>
          </td>
          <td class="td_day bk_kaisai clc" colspan="3">
            <a href="javascript:void(0);" data-pprm-href="/pc/racelist"
               data-pprm-encp="token2" data-pprm-dkbn="1">
              <img src="/pc/static/img/icon/grade/ico_f2.png" />
            </a>
          </td>
        </tr>
        """
        items = discover_events(schedule, year=2016, month=1)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].metadata["venue_code"], "13")
        self.assertEqual(items[0].metadata["grade"], "F1")
        self.assertEqual(items[0].request_method, "POST")
        self.assertEqual(items[0].form_data["disp"], "PJ0301")


if __name__ == "__main__":
    unittest.main()
