# NAR prediction recovery — 2026-11-24

Status: PARTIAL_RECOVERY / RESEARCH_ONLY. This is a recovery record, not the lost v0.1.0/v0.1.1 prediction specification or a production acceptance.

## Recovery result
- R1: Library/project, GitHub commit/issue/branch/PR and Drive direct-folder discovery performed. Original handoff, v0.1.0 formula and P8–P10 detailed plan not retrieved; 30_analysis was empty when directly read. Do not assume absence everywhere.
- R2: Current canonical generation nar_canonical_v1_201601_202512_g20260917 accepted/published. Manifest/final audit hashes verified against CURRENT. P0.1 correction conditions matched actual metadata (commit 8cda30dccf91ca52ea8c20b5120ba3e544f00967). P1 descriptive policy recovered; P2–P7 conclusions not recovered.
- R3: Exact old model and rejected alternatives unknown. Never label a replacement as original v0.1.0.
- R4: New RECOVERY-PILOT-r0.1, 2025-only dirt, ENTRY, target July–December, previous 180 days, minimum two past observations. All four input partitions matched manifest SHA and rows. History from normal valid prior results only; target/same-day/future forbidden; odds/popularity/payout/snapshot unused. No 2026 data used. DuckDB 2.0.1 / PyArrow 25.0.1 / NumPy 2.2.4 private registry bundle byte verification and isolated SQL smoke passed.
- A: average normalized historical finish = 1-(finish-1)/(valid finish count-1).
- AC: A + 0.25 * n_course/(n_course+3) * (same venue/distance/surface mean - A).
- ACJ: AC + 0.15 * n_pair/(n_pair+20) * (prior jockey/trainer pair mean - 0.5); name+affiliation provisional key. Missing base means unscored; missing adjustment means no adjustment. No fitting.
- Retrospective pilot 7,009 eligible races; 6,810 scorable (97.16%). Top-1 win counts A/AC/ACJ = 1783/1791/1830; top-1 top3 = 3892/3889/3937; winner in predicted top3 = 3462/3489/3501. Same-day/future maximum history date check PASS; 497-row July 15 prefix/full invariance PASS; prediction freeze precedes evaluation. No ROI, no independent untouched test, no promotion.
- R5: Proposed replacement plan REC-P8A (multi-year baseline/identity/leakage/ablation), REC-P8B (venue/time/class/pace fit), REC-P9 (auxiliary features, shrinkage, temporal stability), REC-P10 (candidate freeze, independent validation, evaluation only after freeze). These are NOT the lost P8–P10 definitions. 2026 stays excluded until separate data extension and approved evaluation.
- R6: Private Library artifacts persisted and materialized from their Library IDs; byte-for-byte parity verified.

## Artifact index
Library folder: /地方競馬予想/Recovery_20261124/
- NAR_RECOVERY_HANDOFF_20261124.md — 10354 bytes; SHA256 31066791708187d3e18d72eea11618b393a25082132d926e6c2f4a3343581849
- NAR_RECOVERY_PILOT_20261124.zip — 1510082 bytes; SHA256 3737210f679348a54d714a737ec67351540037d140d098cbdc968617685ae2e3
- ZIP contains exact executed script, input/metric JSON, frozen predictions, venue metrics, P1 descriptive sample and SHA256SUMS. Freeze SHA256 991b6a62fea1a5841b540dc4d63a7e821e4f60a8b939068d37969a0731ef0117.

Do not modify CURRENT, production or historical artifacts. Start further research from REC-P8A unless original evidence is recovered. The original formula and roadmap remain unresolved; keep the recovery version separately labeled. No new raw data, binary predictions or private tokens in Git.
