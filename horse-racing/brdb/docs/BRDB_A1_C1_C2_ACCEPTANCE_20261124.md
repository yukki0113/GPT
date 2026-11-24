# BRDB A1 / C1 / C2 acceptance (2026-11-24 JST)

Research-only; no merge, publication, production or prediction authorization.

## A1 — PASS_RESEARCH_ONLY
- Reviewed open PR #2655 and #2643, changed-file lists and clean mergeability. Main observed: ce818abdf97483dacdd525d9fd510f516c86457d.
- Wheel-first environment: Python 3.13.5, DuckDB 2.0.1, PyArrow 25.0.1, NumPy 2.2.4. Registered wheel bundle SHA-256 ceee50c7f3e7b2dc74bc8401320d1b69e96cee8d7809383b876677c74c7caa16. Dependency report success.
- Analysis manifest SHA-256 39b4e94d31e5dc9507bd3aa037aa227c7c8dcefe0ddf3f744ec1e687a6965f1d; 11/11 annual Parquet files verified.
- Accepted M7 PACI-derived cohort reused; raw PACI SHA checked and D4 identities/parents compared. Raw parser was not rerun.
- Replayed v0.6 SHA-256 2d806475886904dcf929a1455e7882ee5aa63e58d60f383da0ffcf4fa41d5f77 matches previous acceptance. 18 horses, 127 selected observations, 78 primary, 17 cross-lane alignments.
- Private relative join: 75 relative records, 375 scope observations, 285 zero cells, 14 condition links across 7 horses. Going-state and historical as-of limitations retained; nested scopes are not independent.
- CI at tested implementation commit 0806045592890a23b55c08b6268f70d9b75a1afa: BRDB run 45328736380 and transverse run 45328736203 passed.

## C1 — PASS_RESEARCH_ONLY
- Fixed overlapping scope sums in projection: retain five separate scopes, preserve zero/missing/inconsistent semantics, explicitly forbid summing.
- Tested source blob 1d75e4c7c29d8c5e853687c30ffa559c6ddb9495; canonical schema blob a8bf85ec7f64a917cfc815253ac70f4b25e0ba8e.
- Real private projection 18/18, Draft 2020-12 validation PASS, two regenerations byte-identical. SHA-256 32705d0b179f96084c21e6aef96595ed8167791bbdc3251df2575aa6d3dcdcd0.

## C2 — PASS_RESEARCH_ONLY
- Actual #2643 source at cd0edb6aaad2f163c971684e62008a6084f597ad, JS blob 880f910e1c9411038edb42a43d178dca709e4227, executed in Node VM with stub DOM.
- Base and merged newspaper: each 18/18 identity joins and rendered HTML, 216 negative guard rejections, other namespaces and original raw inputs unchanged.
- No real browser/device check; C3 remains open. Existing newspaper schema residuals remain separate.

## Evidence retention and gates
Private horse-level files and receipts retained in personal Library /BRDB/Development_C1_C2_20261124/. No horse-level data committed or published. B1 proceeds independently; no downstream training population authorization. C3-C6 and all production gates remain open. This report records tested source revisions, not acceptance of future changes.
