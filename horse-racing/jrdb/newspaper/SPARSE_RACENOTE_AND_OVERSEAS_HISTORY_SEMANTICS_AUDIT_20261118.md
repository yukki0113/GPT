# JRDB Newspaper: sparse RaceNote and overseas history number semantics / consumer impact — 2026-11-18

Status: **SOURCE + REAL-PACI RECONSTRUCTION AUDITED; OFFLINE CANDIDATE 36/36 SCHEMA PASS; PWA / MOMOTARO REGRESSION TEST IN PR; NO LIVE CODE / RELEASE CHANGE**.

Tracking defects: [#2637](https://github.com/yukki0113/GPT/issues/2637) and [#2638](https://github.com/yukki0113/GPT/issues/2638). Parent M7: [#2628](https://github.com/yukki0113/GPT/issues/2628). Prior [real Newspaper preflight](../brdb/placeholder) is actually at `../../brdb/docs/BRDB_M7_REAL_NEWSPAPER_IDENTITY_ADDON_NONINTERFERENCE_20261118.md`.

## Source of truth inspected

- `horse-racing/jrdb/docs/RaceNote_Newspaper_Output_Contract_v0_1.md` is an **all-horse**, per-day legacy handoff; explicitly includes unmarked horses and complete ranks 1..N.
- Current `horse-racing/jrdb/src/jrdb_newspaper_merge_external.py` separately supports `racenote_sparse_marks=True` and `load_racenote(... sparse_marks=True)`: **exactly ranks 1..5 per race**, strict race/horse-name/date/race-key match for the five provided selections. The actual `RaceNote_20261115_PWA_Prediction_Sparse_v056.csv` has 36 races / 180 selected entries, 5 per race.
- The same merge clears prior `addons.racenote_prediction` to prevent stale marks from surviving replacement, and only reattaches a dict for selected horses. This **deliberately leaves the key absent** for unselected horses; it does not mean `mark=×`, negative rating, an unscored horse is unsuitable, or an unknown canonical horse identity.
- `metadata.source_status.racenote_prediction=READY` in sparse mode refers to the **provided selected records**, not all full-field runners. For Tokyo12R `05265412`: five selections `1,3,9,10,18`, still eighteen canonical Newspaper runners.
- `horse-racing/jrdb/schema/jrdb_pwa_newspaper_race_schema_v0_1.json` has `addons.required` containing `racenote_prediction`, allowing the value `object|null` but **not key omission**. Therefore the merger's sparse omission violates the frozen delivery schema even though its selection semantics are internally consistent. This is a **contract alignment defect**, not a new prediction request.

## Overseas past-run number: actual bytes and evidence boundary

- Input: exact `PACI261115.zip`, SHA-256 `3c80e70a74a13874a82b7f7cf4c5f9415d6abbf186ec0ccfa1d2842e51a7b050`; full-field Newspaper reconstruction (not a historically published immutable revision).
- The Tokyo11R `05265411` runner #18, **フォーチュンタイム**, has linked first historical record `ZED261115.txt`, `result_key=2110138420260214`, `race_key=80262EA4` on `2026-02-14`. In the exact 374-byte raw ZED record, zero-indexed byte slice `record[8:10]` is ASCII `b'00'`. The common `jrdb_raw.Parser.sed` decoder (ZED byte-compatible) emits `horse_no=0`; `jrdb_newspaper_build._history_from_zed` copies that 0 into `history[0].horse_no` with no imputation. The raw data is **not corrupted by the Newspaper renderer**.
- The race has venue code `80`, turf distance 1351 m, 13 runners, and **finish=6**. JRDB's official code list maps venue `80` to Saudi Arabia: https://jrdb.com/data_introduction/jrdb_code.html. JRA's 2026 overseas history confirms the horse/race/day/sixth-place: https://www.jra.go.jp/keiba/overseas/historia/2026.html.
- **Do not assert a documented JRDB SED-specific definition that has not been independently verified**: neither the code table nor the raw bytes alone proves that `00` in this specific old-result field formally means `UNKNOWN`, `NOT_ASSIGNED`, or `NOT_AVAILABLE`. They do prove that `00` is the source-supplied past-run field, and the documented/current Newspaper schema cannot treat it as a valid horse number. In a future consumer projection, representing *unknown/unconfirmed horse number* as `null` is a defensible **candidate policy**; retain the raw data/provenance and do not turn a starting-gate number into a horse number. Never change the current runner's canonical horse number.
- An external **JRA-VAN JV-Data** specification may use `00` for some unknown overseas numbers, but that is a **different data provider/contract** and does not by itself certify JRDB's precise SED meaning. A JRDB field-level official statement remains desirable before production semantics are frozen.

## Consumer display impact from actual source code

| Consumer/field | Existing behavior | Hypothesized candidate (`missing→null` or `0→null`) |
|---|---|---|
| Personal PWA RN mark | `newspaper-v5.js::newspaperV5AddonValue` gives empty string for missing or null when source READY; placeholder `-` if pending/error | **Same text** in each source state; selected `◎○▲△` remain unchanged. `newspaper-v6.js` uses truthy guard and also treats missing/null the same. |
| Personal PWA historical result | `newspaper-v4.js::newspaperV4ResultLine` only renders the historical horse number if truthy. Both `0` and `null` are hidden. Standard and compact history cells call this function. | **Same HTML** for the affected historical record: 6着 and 13頭 remain; no invented `0番` or lost race. |
| Momotaro automatic Kenshow projection | `build_momotaro_newspaper_projection.py::automatic_kenshow_prediction` normalizes both absent and `None` to an empty dict; `automatic_kenshow_race_confidence` collects nonblank selected confidences only | **Same automatic candidate/prediction and race confidence** for unselected null vs missing; other contributor values/projections remain separate. |
| Current PWA base validator | `newspaper.js::validateBundle` enforces **current** `horse.key.horse_no` and historical date/sequence, but not min `history[*].horse_no` | Both old `0` and proposed historical `null` pass its limited checks; **strict Draft2020-12 Schema** still rejects historical 0. |
| Schema | `addons.racenote_prediction` required but null allowed; past-run `horse_no` type integer/null, min 1 | **Candidate becomes valid under existing schema without widening requiredness**. |

**Important limitation:** source-level PWA renderer comparisons are **not** screenshots or iPhone/Android/browser end-to-end testing. Need a separate device acceptance for any shipped change. Momotaro's actual full-day projection must be retested before shipping.

## Offline, private, real full-day candidate test

Input: prior exact reconstruction `PACI261115.zip`, 36 Newspaper race JSONs, unmodified existing merger with real v056 sparse CSV. Every candidate is a **deep copy** of each merged JSON; the original file paths and byte SHA never change.

Candidate-only changes:
1. If `addons.racenote_prediction` was absent because no sparse selected row, add the explicit JSON value `null` (never an empty selected prediction, never an inferential score).
2. For the single audited overseas ZED historical record where `history.horse_no=0` (venue `80`, source kind `paci_previous_detail`), change only the **consumer-level** historic number to `null`, preserving 2026-02-14, race `80262EA4`, finish6 and original ZED provenance. Do not change `horses[].key.horse_no`.

Exact measured totals:

| Measurement | Source merged | Offline candidate |
|---|---:|---:|
| Races / current runners | 36 / 505 | 36 / 505 |
| selected real RaceNote marks | 180 | 180 |
| unselected RN addon omitted | 325 | 0 (325 explicit `null`) |
| historical `horse_no=0` | 1 | 0 (one explicit `null`) |
| strict Draft2020-12 race-schema errors | **326** | **0** |
| originally published Newspaper revision | not acquired | **not changed / not verified** |

Audit-only local receipt SHA-256 `2537ab5ab306c3578c9125d6f8e1a759520bfbf110b198293a809ab8081ff84e`. This was an **offline proposal test**, not a production fix. Candidate deep-copy mutations were constrained to exactly those two JSON paths; every other horse/addon/source-status/mark and historic finish/race identity was held constant.

## Safe engineering recommendation and graduation gates

**Recommended schema-preserving change, only after separate code-owner acceptance:**
- For sparse prediction **replacement**, clear each old `addons.racenote_prediction` to explicit `null` rather than popping the key; then overlay exactly the five verified selected row dicts. This preserves no-stale-marks semantics, current required key and nullable type, and existing PWA/Momotaro text outputs.
- At historical ZED→Newspaper **projection**, classify the observed overseas source-provided `00` as a *not-confirmed historical horse number*, project `null`, and record the source's raw `00` provenance. Do **not** reinterpret the runner's current `horse_no`, alter SED/ZED raw records, invent a starting gate, or change the prior finish.
- Add all-day real PACI/CSV, idempotent replacement and re-merge, Personal+Momotaro projection, Current Publish and display-level tests **before** shipping. Strict schema `36/36`, identity `18/18`, all 180 prediction marks unchanged, and previous non-RaceNote addons unchanged are required.
- In advance of release, verify provider-level semantics for `00` if possible, and get explicit approval for the existing Newspaper production module change. **This request authorized audit and display impact verification, not publishing.**
- M7 research identity/addon noninterference PASS and separate M6 scientific BLOCKED remain unchanged. Neither issue #2637 nor #2638 is declared resolved merely because offline candidate is schema-valid.
