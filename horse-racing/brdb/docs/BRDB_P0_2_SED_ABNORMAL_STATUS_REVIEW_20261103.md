# BRDB P0-2 — SED abnormal-code source review (2026-11-03)

**Status: source semantics checked; P0-2/P1-1 formal acceptance still HOLD.**
Research-only documentation. No BRDB CURRENT, PWA, RaceNote, Newspaper, or production change.

## Canonical source and meaning

Source: JRDB official original `成績データ仕様書内容の説明`, dated 2020-07-05, section `異常区分`, in the approved `00_document/official_specs_20261015` Drive folder.
- [Official JRDB SED explanation](https://docs.google.com/document/d/1nj9RVrZ3FZANoWIjL2-Lb1n-d1T3ZIcf4njN5T1nrZw/edit)
- [Official JRDB SED field specification](https://docs.google.com/document/d/1R8xtAXhGxXC87QjbiWo_9n4gthKIitrpkgsa5bv36Zc/edit): `異常区分` is a one-character field at position 143 in the 376-byte SED record.

| Code | Japanese meaning in JRDB source | Concept for research |
| --- | --- | --- |
| 0 | 異常なし | normal status (use validated finish for normal finisher) |
| 1 | 取消 | non-starter |
| 2 | 除外 | non-starter |
| 3 | 中止 | started, did not complete |
| 4 | 失格 | started, disqualified |
| 5 | 降着 | started, demoted placing |
| 6 | 再騎乗 | started / remounted; no observation in the previously reported 2016–2025 cohort |

## Prior full-data observed counts (not rerun in this review)

These figures are transcribed from the independent 2026-11-02 P0-2 replay report and PR #2340 audit comments, rather than re-counted against SED raw data on 2026-11-03.

| Code | Reported entries |
| --- | ---: |
| 0 | 477,650 |
| 1 | 748 |
| 2 | 1,000 |
| 3 | 2,208 |
| 4 | 1 |
| 5 | 20 |
| **Total KYI/SED entries** | **481,627** |

Under **code-based** classification, estimated actual-start records =
`0+3+4+5+6 = 479,879`, excluding `1+2 = 1,748` declared non-starters.
There are 2,229 started records outside code 0.
No code 6 is present in the previously reported count table.

This computed 479,879 is a **derived code-based count**, not an independently reproduced query or an already implemented P0-2 `actual_starters` metric. Preserve the current `actual_starters=null` contract until it has an explicit versioned rule, tested handling for unknown or malformed codes, and a new full-data replay.

## Required metric separation

- `KYI entries`: registrations; not all actual starters.
- `normal_finishers`: existing P0-2 / P1-1 denominator `abnormal_code='0' AND finish BETWEEN 1 AND 18`; the reported 477,650 is a **normal-finish** cohort, not starters.
- `actual starters`: exclude 1 and 2, include 3/4/5/6 as started under official JRDB definitions, with explicit treatment of any unknown/null codes and finish anomalies.
- `P1-1`: keep existing NORMAL_FINISHERS descriptive denominator; do not silently change rates to actual-starter denominators.

## Other gates remain open

1. Archived real-data-tested P0-2/P1-1 Python bytes must be reconciled with the committed GitHub implementations, **or** the exact committed revisions must be replayed on full private inputs.
2. Replay both P0-2 and P1-1 from the same pinned commit/approved input SHA set using common DuckDB 1.1.3, with schema/row multiset equivalence and output audits.
3. Add an explicit versioned starter classification and synthetic edge tests if actual starters are to be exposed; avoid replacing the original descriptive win-rate denominator by implication.
4. Only after these checks, review and merge #2340 before stacked #2342. Until then keep both Draft/HOLD.

Source provenance does not eliminate the unresolved as-of limitation: `STATIC_LATER_SELECTED_SNAPSHOT_NOT_ASOF_VERIFIED` and `prediction_safe=false` remain mandatory.
