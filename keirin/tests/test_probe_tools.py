from __future__ import annotations

from email.message import Message
from hashlib import sha256
from http.client import HTTPResponse
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError

from keirin_probe.capture import (
    CachedRequestError,
    CaptureRequest,
    execute_requests,
)
from keirin_probe.detail_probe_runner import (
    APPROVED_RACE_KEYS,
    build_detail_requests,
    load_reviewed_contract,
    load_sample_spec,
)
from keirin_probe.js_contract_analyzer import analyze_generation
from keirin_probe.official_js_capture import DEFAULT_ASSET_PATHS, load_evidence


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200, headers: Message | None = None, url: str = "https://keirin.jp/test"):
        self.body = body
        self.status = status
        self.headers = headers or Message()
        self.url = url

    def read(self) -> bytes:
        return self.body

    def geturl(self) -> str:
        return self.url

    def getcode(self) -> int:
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def make_http_error(status: int, body: bytes, headers: Message | None = None) -> HTTPError:
    return HTTPError(
        "https://keirin.jp/pc/static/js/commonSubmit.js",
        status,
        "status",
        headers or Message(),
        BytesIO(body),
    )


class ProbeCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.req = CaptureRequest.build(
            method="GET",
            url="https://keirin.jp/pc/static/js/commonSubmit.js",
            headers={"User-Agent": "test", "Accept": "application/javascript"},
            source_evidence={"raw_sha256": "a" * 64},
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_dry_run_sends_zero_requests(self) -> None:
        calls = []
        result = execute_requests(
            [self.req],
            generation_dir=self.root / "gen",
            cache_index=self.root / "cache.json",
            opener=lambda *_a, **_k: calls.append(True),
            execute=False,
        )
        self.assertEqual(result["status"], "plan_only")
        self.assertEqual(result["requests_sent"], 0)
        self.assertEqual(calls, [])
        self.assertFalse((self.root / "gen").exists())

    def test_host_path_allowlist_rejects_external_or_other_origin(self) -> None:
        with self.assertRaises(ValueError):
            CaptureRequest.build(method="GET", url="https://example.org/js.js", headers={})
        with self.assertRaises(ValueError):
            CaptureRequest.build(method="GET", url="http://keirin.jp/js.js", headers={})
        with self.assertRaises(ValueError):
            CaptureRequest.build(method="GET", url="https://keirin.jp:444/js.js", headers={})

    def test_delay_floor_enforced(self) -> None:
        with self.assertRaisesRegex(ValueError, ">= 3.0"):
            execute_requests(
                [self.req],
                generation_dir=self.root / "gen",
                cache_index=self.root / "cache.json",
                execute=True,
                delay_seconds=2.99,
            )

    def test_sequential_start_gap_is_enforced(self) -> None:
        tick = [0.0]
        sleeps = []
        requests = [
            self.req,
            CaptureRequest.build(
                method="GET",
                url="https://keirin.jp/pc/static/js/PJ0301_c.js",
                headers={"User-Agent": "test"},
            ),
        ]
        result = execute_requests(
            requests,
            generation_dir=self.root / "gen",
            cache_index=self.root / "cache.json",
            execute=True,
            opener=lambda *_a, **_k: FakeResponse(b"ok"),
            clock=lambda: tick[0],
            sleep=lambda delay: (sleeps.append(delay), tick.__setitem__(0, tick[0] + delay)),
        )
        self.assertEqual(result["requests_sent"], 2)
        self.assertEqual(sleeps, [3.0])

    def test_redirect_is_saved_and_stops_without_follow(self) -> None:
        calls = []
        headers = Message()
        headers["Location"] = "https://keirin.jp/elsewhere"

        def opener(*_a, **_k):
            calls.append(1)
            raise make_http_error(302, b"redirect", headers)

        result = execute_requests(
            [self.req],
            generation_dir=self.root / "gen",
            cache_index=self.root / "cache.json",
            execute=True,
            opener=opener,
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["records"][0]["http_status"], 302)
        self.assertEqual(result["records"][0]["redirect_location"], "https://keirin.jp/elsewhere")
        self.assertEqual((self.root / "gen" / result["records"][0]["response_body_file"]).read_bytes(), b"redirect")

    def test_403_and_429_are_saved_then_stop(self) -> None:
        for status in (403, 429):
            with self.subTest(status=status):
                gen = self.root / f"gen-{status}"
                calls = []

                def opener(*_a, **_k):
                    calls.append(1)
                    raise make_http_error(status, b"access denied")

                result = execute_requests(
                    [self.req],
                    generation_dir=gen,
                    cache_index=self.root / f"cache-{status}.json",
                    execute=True,
                    opener=opener,
                )
                self.assertEqual(len(calls), 1)
                self.assertEqual(result["status"], "stopped")
                self.assertEqual(result["records"][0]["http_status"], status)
                body = gen / result["records"][0]["response_body_file"]
                self.assertEqual(body.read_bytes(), b"access denied")

    def test_restriction_text_stops_on_200(self) -> None:
        calls = []
        result = execute_requests(
            [self.req],
            generation_dir=self.root / "gen",
            cache_index=self.root / "cache.json",
            execute=True,
            opener=lambda *_a, **_k: (calls.append(1) or FakeResponse("アクセスを制限しています".encode())),
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["status"], "stopped")
        self.assertTrue(result["records"][0]["restriction_text_detected"])

    def test_transport_failure_is_not_retried(self) -> None:
        calls = []

        def opener(*_a, **_k):
            calls.append(1)
            raise OSError("offline")

        result = execute_requests(
            [self.req],
            generation_dir=self.root / "gen",
            cache_index=self.root / "cache.json",
            execute=True,
            opener=opener,
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["records"][0]["transport_error"], "OSError: offline")

    def test_no_refetch_is_durable_across_generation(self) -> None:
        calls = []
        opener = lambda *_a, **_k: (calls.append(1) or FakeResponse(b"ok"))
        cache = self.root / "cache.json"
        execute_requests(
            [self.req],
            generation_dir=self.root / "first",
            cache_index=cache,
            execute=True,
            opener=opener,
        )
        with self.assertRaises(CachedRequestError):
            execute_requests(
                [self.req],
                generation_dir=self.root / "second",
                cache_index=cache,
                execute=True,
                opener=opener,
            )
        self.assertEqual(len(calls), 1)
        self.assertFalse((self.root / "second").exists())

    def test_generation_output_is_immutable(self) -> None:
        execute_requests(
            [self.req],
            generation_dir=self.root / "same",
            cache_index=self.root / "cache.json",
            execute=True,
            opener=lambda *_a, **_k: FakeResponse(b"first"),
        )
        with self.assertRaises(FileExistsError):
            execute_requests(
                [self.req],
                generation_dir=self.root / "same",
                cache_index=self.root / "other-cache.json",
                execute=True,
                opener=lambda *_a, **_k: FakeResponse(b"second"),
            )
        body = next((self.root / "same" / "responses").glob("*.body"))
        self.assertEqual(body.read_bytes(), b"first")

    def test_response_headers_and_bytes_are_captured(self) -> None:
        headers = Message()
        headers["Content-Type"] = "application/javascript"
        body = b"window.location='/pc/racelive';"
        result = execute_requests(
            [self.req],
            generation_dir=self.root / "gen",
            cache_index=self.root / "cache.json",
            execute=True,
            opener=lambda *_a, **_k: FakeResponse(body, headers=headers),
        )
        record = result["records"][0]
        self.assertEqual(record["response_sha256"], sha256(body).hexdigest())
        self.assertEqual((self.root / "gen" / record["response_body_file"]).read_bytes(), body)
        self.assertIn(["Content-Type", "application/javascript"], record["response_headers"])


class ContractAndAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_js_evidence_spec_path_allowlist_and_raw_provenance(self) -> None:
        evidence = {
            "assets": [
                {
                    "path": path,
                    "purpose": "fixture",
                    "references": [
                        {
                            "raw_sha256": "a" * 64,
                            "script_src_values": [path],
                        }
                    ],
                }
                for path in sorted(DEFAULT_ASSET_PATHS)
            ]
        }
        path = self.root / "evidence.json"
        path.write_text(json.dumps(evidence), encoding="utf-8")
        self.assertEqual(len(load_evidence(path)["assets"]), 3)
        evidence["assets"][0]["path"] = "/outside.js"
        path.write_text(json.dumps(evidence), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_evidence(path)

    def test_sample_spec_rejects_nonapproved_race(self) -> None:
        value = {
            "samples": [
                {
                    "race_key": key,
                    "detail_token": "opaque",
                    "source_raw_sha256": "a" * 64,
                }
                for key in sorted(APPROVED_RACE_KEYS)
            ]
        }
        value["samples"][0]["race_key"] = "19990101|01|1"
        path = self.root / "samples.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "five approved"):
            load_sample_spec(path)

    def test_malformed_or_unreviewed_contract_rejected(self) -> None:
        path = self.root / "contract.json"
        path.write_text(json.dumps({"review_status": "draft"}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "review_status"):
            load_reviewed_contract(path)

    def test_valid_reviewed_contract_builds_only_five_fixed_route_requests(self) -> None:
        samples = [
            {"race_key": key, "detail_token": f"t-{i}", "source_raw_sha256": "b" * 64}
            for i, key in enumerate(sorted(APPROVED_RACE_KEYS))
        ]
        contract = {
            "review_status": "reviewed",
            "reviewer": "offline-test",
            "reviewed_at": "2026-09-29T00:00:00Z",
            "endpoint": {"scheme": "https", "host": "keirin.jp", "path": "/pc/racelive"},
            "method": "POST",
            "encoding": "form",
            "token_field": "racedetail",
            "mode_field": None,
            "headers": {"User-Agent": "test"},
            "contract_source": [{"file": "official.js", "observed_behavior": "builds body"}],
        }
        requests = build_detail_requests(samples, contract)
        self.assertEqual(len(requests), 5)
        self.assertTrue(all(r.url == "https://keirin.jp/pc/racelive" for r in requests))
        self.assertTrue(all(r.method == "POST" for r in requests))
        self.assertTrue(all(b"racedetail=" in r.body for r in requests))
        contract["endpoint"]["host"] = "example.org"
        path = self.root / "contract.json"
        path.write_text(json.dumps(contract), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "endpoint"):
            load_reviewed_contract(path)

    def test_cookie_and_unapproved_header_rejected(self) -> None:
        base = {
            "review_status": "reviewed",
            "reviewer": "test",
            "reviewed_at": "now",
            "endpoint": {"scheme": "https", "host": "keirin.jp", "path": "/pc/racelive"},
            "method": "GET",
            "encoding": "query",
            "token_field": "token",
            "headers": {"Cookie": "sid=x"},
            "contract_source": [{"file": "x.js", "observed_behavior": "literal"}],
        }
        path = self.root / "contract.json"
        path.write_text(json.dumps(base), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "headers"):
            load_reviewed_contract(path)

    def test_analyzer_reports_keyword_span_and_preserves_unknown_confidence(self) -> None:
        generation = self.root / "capture"
        response_dir = generation / "responses"
        response_dir.mkdir(parents=True)
        script = b"function goRace(token) { var url='/pc/racelive'; form.submit(); }"
        body_path = response_dir / "script.body"
        body_path.write_bytes(script)
        manifest = {
            "status": "complete",
            "records": [
                {
                    "http_status": 200,
                    "requested_url": "https://keirin.jp/pc/static/js/test.js",
                    "response_body_file": "responses/script.body",
                    "response_sha256": sha256(script).hexdigest(),
                }
            ],
        }
        (generation / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        result = analyze_generation(generation)
        self.assertGreaterEqual(result["evidence_count"], 3)
        hit = next(item for item in result["evidence"] if item["term"] == "/pc/racelive")
        self.assertEqual(hit["symbol"], "goRace")
        self.assertEqual(hit["confidence"], "Unknown")
        self.assertEqual(result["conclusions"], [])

    def test_analyzer_rejects_hash_mismatch(self) -> None:
        generation = self.root / "capture"
        (generation / "responses").mkdir(parents=True)
        (generation / "responses/a.body").write_bytes(b"actual")
        (generation / "manifest.json").write_text(
            json.dumps({
                "status": "complete",
                "records": [{
                    "http_status": 200,
                    "requested_url": "https://keirin.jp/script.js",
                    "response_body_file": "responses/a.body",
                    "response_sha256": "0" * 64,
                }],
            }),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            analyze_generation(generation)


if __name__ == "__main__":
    unittest.main()
