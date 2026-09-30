# Stage B1 Probe Toolchain Runbook

Date: 2026-09-29
Implementation base: latest main at start of work; no network request was made to KEIRIN.JP.

## What is implemented

- keirin_probe.official_js_capture: fixed host and three-path allowlist from the five existing Raw documents; plan-only unless --execute.
- keirin_probe.capture: sequential HTTP capture, >=3 second request-start spacing, no retry, no CookieJar/auth headers, no automatic redirect following, immutable response files, response headers and request metadata, SHA-256, durable request identity cache, and stop-on-restriction logic.
- keirin_probe.js_contract_analyzer: local-only search over captured script bytes with file, symbol candidate, line, byte range, exact text/context, and default Unknown confidence. It emits no semantic conclusions automatically.
- keirin_probe.detail_probe_runner: accepts exactly the approved five race keys and refuses execution unless a reviewed request-contract JSON is supplied. It cannot target any host/path except https://keirin.jp/pc/racelive, allows only reviewed non-session headers, sends at most five requests, and reuses the same capture/no-refetch/fail-close logic.
- probe_specs/stage_b1_js_asset_evidence_20260929.json: exact script paths tied to the immutable Raw member path and SHA-256 for the 2016, 2020, 2025-standard, 2025-Girls, and 2025-advance sample event HTML. Purpose notes do not claim that a script's function has already been proven.
- probe_specs/detail_probe_samples_20260929.json: the five Stage A sample keys and source HTML SHA-256 values. Opaque detail tokens are deliberately not committed; populate them from the local Stage A Canonical before supplying a reviewed contract.

Only these JavaScript paths are enabled: /pc/static/js/commonSubmit.js, /pc/static/js/PJ0301_c.js, and /pc/static/js/FPJ0305.js. No crawling or transitive URL discovery is implemented. If local offline analysis proves another referenced script is necessary, add it only after verifying its exact script src and source Raw SHA, documenting why, and reviewing a minimal allowlist change.

## Offline tests

From keirin/:

~~~bash
PYTHONPATH=. python -m unittest tests.test_probe_tools -v
python -m py_compile keirin_probe/*.py
~~~

Tests use mocked local responses only. They cover dry-run zero requests, host/path and source evidence allowlists, minimum interval enforcement, sequential start spacing, redirect/403/429/restriction stop, no retry, immutable output, cache/no-refetch, exact five-race validation, reviewed-contract validation, and analyzer evidence spans/hash verification.

## Stage B1 handoff

1. Review and merge the code/spec through the normal GitHub PR workflow.
2. On a permitted local system, provide an explicit output root and run the no-network plan first:

~~~bash
cd keirin
PYTHONPATH=. python -m keirin_probe.official_js_capture \
  --evidence-file probe_specs/stage_b1_js_asset_evidence_20260929.json \
  --output-root /path/to/keirin_probe_capture \
  --generation KEIRIN_JS_B1_20260929_01 \
  --delay-seconds 3
~~~

This plan command is safe and sends zero HTTP requests.

3. In the explicitly permitted local environment only, the execution command is:

~~~bash
cd keirin
PYTHONPATH=. python -m keirin_probe.official_js_capture \
  --evidence-file probe_specs/stage_b1_js_asset_evidence_20260929.json \
  --output-root /path/to/keirin_probe_capture \
  --generation KEIRIN_JS_B1_20260929_01 \
  --delay-seconds 3 \
  --execute
~~~

Do not run it in Work. Do not use a browser, cookie jar, proxy, alternate host, or GitHub Actions merely to route around the Work egress restriction. Any redirect, non-success status, 403/429, transport failure, or restriction phrase saves available response evidence and stops the generation. Never retry the same request identity.
4. Expected capture layout:

~~~text
/path/to/keirin_probe_capture/
  request-cache.json
  KEIRIN_JS_B1_20260929_01/
    manifest.json
    requests/                 # exact request body bytes, if any
    responses/
      01_<request-id>.body
      01_<request-id>.headers.json
      ...
~~~

The JS requests are GET and have no request body. The manifest retains source Raw path/SHA evidence, method, URL, request headers, timestamps, elapsed time, response status, redirect location, observable ordered response headers, final URL, response length/SHA, and stop outcome. Keep response files unchanged. Return the entire generation directory, including its manifest, for offline analysis.
5. With the returned capture:

~~~bash
cd keirin
PYTHONPATH=. python -m keirin_probe.js_contract_analyzer \
  --capture-generation /path/to/keirin_probe_capture/KEIRIN_JS_B1_20260929_01 \
  --output /path/to/keirin_probe_capture/js_contract_evidence.json
~~~

This reads local files only and refuses hash mismatches. Review actual request-construction code, not just variable names. Record each finding with source file/symbol/line or byte span, behavior, and confidence before preparing a contract.
6. Only after that review, create a contract JSON with review_status: "reviewed", reviewer, review timestamp, the fixed endpoint, method, query/form encoding, token field, optional mode field/value, reviewed headers, and source evidence quoting the exact official-JS request-construction behavior. The runner rejects a draft or malformed contract; it never assumes encp/disp.
7. The detail runner's plan mode (no network) can be used before authorization:

~~~bash
cd keirin
PYTHONPATH=. python -m keirin_probe.detail_probe_runner \
  --sample-spec probe_specs/detail_probe_samples_20260929.json \
  --output-root /path/to/keirin_detail_probe \
  --generation KEIRIN_DETAIL_PROBE_20260929_01
~~~

With no contract, it reports plan_blocked_contract_missing without needing tokens. To plan the five concrete requests, supply a local sample JSON populated with the tokens from Stage A Canonical and a reviewed contract, but omit --execute. Actual requests require both that reviewed file and an explicit --execute; the project owner must separately authorize that next phase. It remains limited to these five samples and has no bulk mode.

No five-race request contract is included because Stage B0 did not establish a wire mapping. No detail probe was executed and no bulk collection was started.
