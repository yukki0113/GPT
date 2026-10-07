# EdgeDB v0.5 First Surface + First Blinkers Full-History Aggregation

Status: PARTIAL_WITH_TOPOLOGY_BLOCKED

## Input provenance

- Warehouse run 37592837881, artifact ID 11468713930, digest `sha256:fb28c17889cf2a9028b58e1bac3164b89a0b4c66eadfb5d3dba19d1ace88499a`; generation `jrdb_normalized_warehouse_v1_2010_2025_g20260921`.
- Feature Mart run 36116777782 / `sha256:19d713da2e6ebf57965de98952fbf18d79f9ddfd5c1996833af3267b1a53f725`.
- Analysis run 36437363166 / `sha256:d159c2fca9959d9b144d55f9b3ba98228158cc38b85fcc730032a53f29252a55`.
- Instruction commit `a39cb1372c1446da457fba2f564e3b86bee2364b`; execution source commit `c4957de57b04aa8f1234e7cf725c3dd5d748ba92`.

## Warehouse verification

- 32/32 annual partitions verified against embedded SHA256 and byte sizes; KYI 16, SED 16; years 2010-2025.
- SED rows 781,161; reconciled events 781,161; duplicate groups collapsed 0; conflicting groups 0.
- KYI rows 781,161; duplicate groups collapsed 0; conflict/unjoined groups 0.
- Canonical identity is blood registration number; target joins cross-check race_key_raw, horse_no, race_date and Feature Mart horse_id. Names are not used.
- Any identity/surface conflict, same-day multi-race ambiguity, or left-boundary first observation remains UNKNOWN.
- 2010-2025 gives at least 12 years of context for 2022-2025 target starts; normal JRA career ages are below that horizon. Identities first observed in 2010 are still explicitly censored to UNKNOWN, covering exceptional longevity or pre-2010 starts.

## First surface audit

- FIRST_DIRT candidate memberships: 7,850; UNKNOWN history rows: 0.
- FIRST_TURF candidate memberships: 7,073; UNKNOWN history rows: 0.
- History join status: `{"MATCHED": 189957}`.
- Flags use strict earlier race_date; the target row is excluded. Same-day duplicate/source rows are collapsed on canonical identity and conflicting/multiple-race dates are UNKNOWN.

## First blinkers audit

- Chronology-derived active-first rows: 14,078; code==1 rows: 15,027; parity mismatches: 657.
- Warehouse code distribution: `[{"code": "1", "count": 15027}, {"code": "2", "count": 3372}, {"code": "3", "count": 52599}, {"code": "<BLANK>", "count": 710163}]`.
- UNKNOWN blinkers target rows: 205. Mismatches are UNKNOWN for candidate membership; see `output/first_history_audit.json` in the Actions artifact for representative rows; the checked-in audit stores anonymized mismatch patterns.
- Active semantics follow the repository codebook: 1=first worn, 2=re-worn, 3=active blinkers. Blank code means no active blinkers on that start; code 2 is not accepted as first use when codebook and chronology disagree.

## Unified candidate counts

| Family | All candidates | n>=5 | Positive Value | Negative Edge | Support classes | Freshness | LONGSHOT_EVIDENCE |
|---|---:|---:|---:|---:|---|---|---:|
| T1 | 800 | 725 | 100 | 114 | `{"LARGE": 550, "MEDIUM": 106, "MICRO": 46, "RAW_ONLY": 75, "SMALL": 23}` | `{"CURRENT": 321, "DECAYING": 166, "EMERGING": 43, "INSUFFICIENT_HISTORY": 15, "OLD_ONLY": 3, "VOLATILE": 177}` | 614 |
| T2 | 12939 | 4767 | 1102 | 1679 | `{"LARGE": 191, "MEDIUM": 1004, "MICRO": 2076, "RAW_ONLY": 8172, "SMALL": 1496}` | `{"CURRENT": 659, "DECAYING": 804, "EMERGING": 80, "INSUFFICIENT_HISTORY": 1845, "OLD_ONLY": 17, "VOLATILE": 1362}` | 1724 |
| T3 | 928 | 523 | 93 | 138 | `{"LARGE": 177, "MEDIUM": 80, "MICRO": 164, "RAW_ONLY": 405, "SMALL": 102}` | `{"CURRENT": 134, "DECAYING": 84, "EMERGING": 9, "INSUFFICIENT_HISTORY": 160, "VOLATILE": 136}` | 288 |
| T4 | 1420 | 600 | 117 | 259 | `{"LARGE": 153, "MEDIUM": 170, "MICRO": 162, "RAW_ONLY": 820, "SMALL": 115}` | `{"CURRENT": 118, "DECAYING": 124, "EMERGING": 10, "INSUFFICIENT_HISTORY": 176, "OLD_ONLY": 1, "VOLATILE": 171}` | 305 |
| T5 | 264 | 102 | 22 | 44 | `{"LARGE": 4, "MEDIUM": 35, "MICRO": 31, "RAW_ONLY": 162, "SMALL": 32}` | `{"CURRENT": 16, "DECAYING": 19, "INSUFFICIENT_HISTORY": 30, "VOLATILE": 37}` | 40 |
| T6 | 1614 | 1024 | 186 | 104 | `{"LARGE": 353, "MEDIUM": 199, "MICRO": 262, "RAW_ONLY": 590, "SMALL": 210}` | `{"CURRENT": 242, "DECAYING": 197, "EMERGING": 20, "INSUFFICIENT_HISTORY": 306, "OLD_ONLY": 5, "VOLATILE": 254}` | 572 |

Unified inventory: 17,965 raw candidates; 7,741 with n>=5.
Positive Value remains exactly `n >= 5 AND combined 2024-2025 place ROI >= 100%`; no threshold or support floor changed. No popularity, payout, or odds field defines candidate membership.

## History-dependent family counts

| Template | Candidates | n>=5 | Positive Value | Negative Edge |
|---|---:|---:|---:|---:|
| T4_SIRE_FIRST_DIRT | 389 | 179 | 40 | 62 |
| T4_SIRE_FIRST_TURF | 375 | 157 | 28 | 64 |
| T5_SIRE_FIRST_BLINKERS | 264 | 102 | 22 | 44 |

## Representative examples

- T4_SIRE_FIRST_DIRT Positive Value example: v05-2fe971daf26b437b3dae8961 — リアルスティール産駒 (n=168, places=34, place ROI=109.1%). Its parent-relative place-rate diagnostic is negative while absolute recent ROI passes the Value gate; these lanes remain separate.
- T4_SIRE_FIRST_TURF: v05-9b9c29270c6d353943b4079f — エピファネイア産駒は初芝でプラス (n=247, places=103, place ROI=107.3%).
- T5_SIRE_FIRST_BLINKERS: v05-23ea553ddd266354a33eec03 — ホッコータルマエ産駒は初ブリンカーでプラス (n=44, places=11, place ROI=140.9%).
- MICRO longshot: v05-aad8ae82def6ea6fb84cb400 (アルバート産駒は初ダートでプラス, place ROI 152.0%).
- Negative Edge: v05-116cf3e753567e0eae21c369 (アドマイヤムーン産駒は初ダートでマイナス).

## Existing-family parity

PASS: 7,303 existing candidate IDs matched the merged PR #1871 baseline. For each, n, combined place ROI, positive Value eligibility, and negative Edge eligibility were identical. The unified inventory retains those rows plus all three added template families.

## Output artifacts and tests

- Durable compact audits and this report are committed under `collab/results/`.
- Combined candidate summary, history-dependent candidate summary, raw/research Parquet tables, and run logs are retained in Actions artifact `data-storage-fallback-37595872503` (artifact ID 11469728874; digest `sha256:76dd58a7149cc61b389c9f903c739beee1b6b41ff9e024bb942e9cf817799f17`).
- Focused tests: 17 passed, covering the existing v0.5 contracts plus warehouse hash/partition verification, first-history chronology, duplicate reconciliation, blank/no-blinker handling, unknowns, re-wear, deterministic IDs, and frozen ROI/support gates.

## Recommendation

`PARTIAL_WITH_TOPOLOGY_BLOCKED`. The original T1-T6 families plus FIRST_DIRT/FIRST_TURF/FIRST_BLINKERS are now on the same frozen rule set. Course topology remains blocked because no authoritative turn-count crosswalk exists. Production impact NONE.
