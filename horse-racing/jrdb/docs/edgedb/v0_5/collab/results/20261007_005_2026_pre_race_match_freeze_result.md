# 20261007_004 — 2026 Pre-Race Match Freeze Source Audit

Status: BLOCKED — no match freeze created  
Recommendation: `MATCHER_CONTRACT_BLOCKED`  
Production impact: NONE

## Scope and boundary

This audit verified the frozen Turn 1 cohort and audited the canonical 2026 daily KYI source route. It did not build or publish a 2026 fact mart or match freeze. No 2026 outcomes, finish positions, payouts, popularity, odds, or result-side Analysis fields were read or used. Turn 3 was not started.

## A. Input provenance

- Frozen cohort: `horse-racing/jrdb/config/edgedb/v0_5/frozen/v05_positive_value_frozen_cohort.json`
- Cohort SHA-256: `a85a7ee86dc21b6e081fd5a637245b06a2ba23eef2e22628a14468b004e2cdc9` — verified against Turn 1 artifact JSON.
- Turn 1 source: run `37598903743`, artifact `11471917437`, `edgedb-v05-positive-value-freeze-37598903743`; the instruction-provided frozen Parquet SHA is `a57c9dcbc9c8c93d9c88e98a0db26818b628dbd580c2c9108d20a67adbab425b`.
- Candidate count: 1,620; all cohort JSON entries parsed. No candidates were regenerated.
- 2026 source audit: `fetch_jrdb_history.py`, via existing `jrdb_daily_history_fetch_issue.yml`; run `37602432550`, artifact `11472884532`, artifact name `jrdb-daily-history-20260101-20261007`, digest `sha256:1002e3b4dee0ed9bdd58dc0ccb7beb522e90148fbdd05936ee19777c157eb10f`.
- Daily archive coverage reported 85 downloaded KYI files and 195 NOT_FOUND dates. NOT_FOUND dates were not assumed to be missing race days.
- Historical 2010–2025 Warehouse / Feature Mart artifacts were not joined in this source audit.

## B. Available 2026 source coverage

The retrieved KYI archive contained 85 dates, from 2026-01-04 through 2026-10-04. A pre-race-only structural scan (record length, race key, horse number) found:

- 85 source dates;
- 2,658 unique race keys;
- 36,861 KYI rows;
- 36,706 unique race-horse keys;
- 155 repeated race-horse keys requiring canonical duplicate reconciliation;
- 0 malformed KYI record lengths.

These counts describe the KYI archive only. They do not establish complete canonical JRA race-day coverage; a canonical calendar/PACI comparison was not available in the retrieved artifact.

## C. Source and schema audit

The current 2026 source generation available through the existing daily route is KYI only. Its safe structural key is the race key plus horse number; the source parser exposes runner attributes such as registration number, frame, and blinker code. This is not a complete v0.5 matching fact schema.

The frozen cohort requires the following condition fields across its 1,620 exact condition objects: `distance_m`, `frame_no`, `going_bucket`, `sire_name`, `surface_code`, `venue_code`, `distance_change`, `surface_transition`, `first_dirt`, `first_turf`, and `first_blinkers`. The KYI-only artifact does not establish a complete canonical source for race distance, surface, going, sire name, or the 2026 race-by-race PACI/Feature Mart generation. No complete matching schema can be allowlisted from this artifact alone.

A separate 2026 historical-start source is also needed to derive incremental FIRST_DIRT/FIRST_TURF/FIRST_BLINKERS with strict chronology. This turn did not inspect any SED result fields or substitute them for that source.

The cohort contains 1,620 parseable candidate objects. The matcher was not executed, so unsupported-key fail-closed behavior and exact matching support are **not tested**.


### Required condition field availability

The source schema below is the repository's safe KYI record parser schema plus its composite key definition. It is not a fact-mart schema.

| Frozen condition field | KYI availability | Notes |
|---|---|---|
| `frame_no` | Present | Parsed from the pre-race KYI row. |
| `venue_code` | Present in canonical race key | Race key's first two characters; date is represented by the archive date, while race key preserves venue/meeting/day/race number. |
| `distance_m` | Not established | No canonical 2026 PACI/Feature Mart source was included in this artifact. |
| `surface_code` | Not established | No canonical 2026 PACI/Feature Mart source was included in this artifact. |
| `going_bucket` | Not established | No permitted pre-race source was included. |
| `sire_name` | Not established | KYI safe parser schema does not expose this field. |
| `distance_change` | Not established | Requires distance plus a canonical strictly earlier start. |
| `surface_transition` | Not established | Requires surface plus a canonical strictly earlier start. |
| `first_dirt` | Not derived | Requires surface and reconciled strictly earlier career starts. |
| `first_turf` | Not derived | Requires surface and reconciled strictly earlier career starts. |
| `first_blinkers` | Not derived | KYI has a blinker code, but the chronology-safe history comparison was not built. |

Canonical runner key in the verified KYI input is `race_horse_key = race_key_raw + horse_no`. Identity is carried by a blood-registration number in the source but is not needed for the structural counts or committed audit. The structural scan read record length, race key, and horse number only. The raw archive is not used as the matching input; parser fields such as odds and ratings were not opened.

## D. Leakage audit

| Check | Status |
|---|---|
| 2026 outcomes or result-side Analysis used | PASS — not used |
| Finish, payout, popularity, or odds read for matching | PASS — no matching was performed |
| Matching fact mart excludes result fields | NOT RUN — no fact mart was created |
| Popularity/odds absent from a matching input | NOT RUN — no matching input was created |
| All matching sources documented | PASS — only the KYI daily artifact was structurally scanned |

## E. History audit

FIRST_DIRT, FIRST_TURF, and FIRST_BLINKERS were not derived. No 2026 incremental-history chronology check was run; chronology violations and UNKNOWN counts are therefore **not measured**, not zero.

## F. Match counts and fingerprints

No match rows were created. Runner density, family/month match counts, maximum matches per runner, pre-race fact fingerprint, match fingerprint, and monthly/day fingerprints are **not available**.

## G. Block reason and next source requirement

The available daily KYI artifact is useful as a runner inventory, but it is insufficient to construct the required canonical pre-race fact population for the frozen conditions. The exact 1,620-candidate matcher therefore cannot be safely run from the verified source inputs. Do not interpret this audit as an empty match set or as full 2026 coverage.

To resume, materialize the canonical 2026 PACI/Edge Feature Mart pre-race source, reconcile the 155 duplicate race-horse keys, provide a permitted chronological-history source for strictly earlier 2026 starts, and verify date coverage against the canonical race calendar. Then build and test the exact-condition matcher without result, odds, or popularity fields.

## H. Recommendation

`MATCHER_CONTRACT_BLOCKED`

Production remains unchanged. No match freeze is available for Turn 3.
