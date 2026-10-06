# 20261006_008 — Observe-only cohort freeze / prospective SHADOW

- Status / decision: **`READY_FOR_NEXT_TRUE_FORWARD_DATE`**
- Exact instruction source commit: `18646e915d800edb1b075a95553470247205dec3`
- Production impact: **NONE**. No v0.2 STANDARD, v0.3 SHADOW, registry, or mark-serving change.
- True-forward date executed: **No**. No clean unseen pre-race date and approved pre-race fact snapshot were available to this task. No historical replay is called prospective evidence.

## Authoritative evidence and selection

The 3y authority is canonical R1 run `37321021557`, source `9aba7103f944ea419189c104be4e48485b819d0d`, result file Git blob SHA `d27f7cdb434f8294b280151da4731fc17b917eb8`. The 5y `PEDIGREE_CROSS` authority is accepted C1/C2A run `37405197661`, C2B run `37405567334`, canonical source `24c4d2b410ed27b663d4a7d618754ae0dbe745c0`, and result file Git blob SHA `68e6343d8ab42ab32401f337c834996da7d00b5f`. Its reporter labels were reproduced unchanged from the accepted R1 classifier; accepted 5y summary labels, family summary, and examples compared exactly with the rerun. No candidate discovery or threshold adjustment occurred.

Local `.venv-data-storage` check returned `DEPENDENCY_MISSING` for DuckDB and PyArrow. The one pinned requirements repair attempt failed at the managed `proxy:8080` connection. The documented Actions fallback was used. The final full-label/template audit [run 37416474375](https://github.com/yukki0113/GPT/actions/runs/37416474375), Issue #1817, was **PASS** with DuckDB 1.1.3 and PyArrow 25.0.1. Artifact `11391276365` archive SHA-256 `b81669aeff5fa73a93bc421e3b8acf775d74f8709329132a0b06dc7eb0d6666b`; full enriched JSON SHA-256 `b75025ff9bab80d74d3ba99170cf7661ff1c27f64c85682081fc1598569ea3df`. The first full-label PASS run `37416164584` lacked template IDs in the export; #1817 retained them without changing labels.

| Family | Historical C2 | Incremental label | Exact definitions retained | Excluded from cohort |
|---|---:|---:|---:|---:|
| `PEDIGREE_CROSS` (accepted 5y) | 9,022 | 266 | 266 | 8,756 non-incremental |
| `PEDIGREE_TRANSITION_CROSS` (accepted 3y) | 4,204 | 81 | 10 | 4,123 non-incremental; 71 incremental definitions unavailable |
| `TRANSITION_CROSS` (stopped) | 1,640 | 20 | 0 | Entire family |

The accepted 3y artifact retains only ten strongest `PEDIGREE_TRANSITION_CROSS` incremental definitions, not the full 81 candidate IDs/conditions. The 3y `shortlist.csv` contains 100 `PEDIGREE_CROSS` rows only. The missing 71 were excluded under the instruction's exact-definition/provenance rule; neither provisional PR #1800/#1801/#1809 nor a new search was used to infer them. For the retained ten, template IDs were uniquely recovered from the accepted Stage B catalog JSON (SHA-256 `4844ccbd0affbad74910a3f1704df524909772d0acb962bba87e870db4f0894a`) and verified against each canonical candidate-ID hash.

## Frozen cohort

- Config: `horse-racing/jrdb/config/edgedb/v0_4/observe_only_cohort_v0_1.json`
- Reproduction metadata: `horse-racing/jrdb/config/edgedb/v0_4/observe_only_cohort_source_v0_1.json`
- Source candidates: **276**. Exact/semantic condition duplicates: **0**. Duplicate map entries: **0**. Deduplicated matcher rows: **276** (266 + 10).
- Fingerprint-set SHA-256: **`02bfabdcd925b804bc1975a61bb1f84914202e75cf2638ec8fa795690df8b11f`**.
- Cohort file SHA-256: **`54722046c1196f945aca3b5b5f0528d71e9919ac448c49a895de788c9f9305db`**.
- Every row is `OBSERVE_ONLY`, `production_eligible=false`, with a unique canonical condition fingerprint. Historical support/ROI and parent incrementality are audit-only. Membership has no market/popularity input. There is no membership rank or cutoff; presentation priority is separate from membership.

## Prospective tooling and contract

- Builder/freezer: `horse-racing/jrdb/src/jrdb_edge_v04_observe_cohort.py`. It reads the accepted full 5y enriched artifact and bounded accepted 3y summary, checks canonical label counts and candidate/template IDs, canonicalizes conditions, records duplicate mappings, and validates the frozen file.
- Pre-race matcher, freeze writer/validator, post-result evaluator: `horse-racing/jrdb/src/jrdb_edge_v04_observe_shadow.py`. It uses exactly the Stage C1 allowed dimensions and its string equality/null omission semantics. Input is JSONL containing `race_date`, `race_id`, `horse_id`, `facts`, and `source`, where `facts` are normal JRDB pre-race values expressed as canonical Edge v0.4 feature names. The adapter's source bytes are hashed. Market/popularity are ignored for matching; result/payout fields anywhere in the source are rejected.
- `freeze` requires a timezone-aware target-date as-of timestamp, hashes source facts, emits all overlapping raw matches and `manifest.json`, and records result-leakage PASS. `validate` checks cohort/freeze hashes, membership, counts, and absent results before the post-result route is opened. Store full day files in the approved data/artifact store; commit only a compact manifest when a real observation is made.
- `evaluate` joins the frozen match IDs to normal JRDB post-result JSONL by date/race/horse. It requires an opened-at time after freeze, records raw and unique-horse views, and reports family, cohort, day, and aggregate metrics. Win/place ROI uses payout per 100-unit stake; overlapping raw ROI is explicitly non-additive. Market/popularity diagnostics are post-freeze only.
- Tests: `python -m unittest discover -s horse-racing/jrdb/tests -p 'test_jrdb_edge_v04_observe_shadow.py'` — **7 passed**. They cover fingerprint order/duplicates, membership tamper rejection, result leakage, market independence, repeated freeze hashes, raw overlap preservation, and post-result timing/unique view. The actual 276-row cohort was also built and validated. These are fixture/tooling tests, not true-forward observations.

Before any later SHADOW catalog or promotion discussion, review multiple distinct race days, independent hits where applicable, meaningful support, payout concentration, interpretability against parents and context, and whether prospective direction conflicts with historical claims. No numeric promotion threshold or production decision is made here.
