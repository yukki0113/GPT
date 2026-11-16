# BRDB D4 — PACI real-field input gate (2026-11-16)

Status: **CODE CANDIDATE / REAL PACI E2E NOT YET ACCEPTED**. This is a follow-on to merged [D4 #2601](https://github.com/yukki0113/GPT/pull/2601). No deployment or prediction authorization.

## Source contract
- Read only a byte-identifiable, explicitly supplied `PACI26xxxx.zip` from the canonical approved JRDB Drive Raw/PACI folder, materialized through the connected Drive path. Do not make a secondary parser or fetch the source from public web.
- Use `horse-racing/jrdb/src/jrdb_raw.py` `Parser`, `canonical_members`, `split_fixed_records` for BAC/KYI/UKC.
- Read **one exact race_key**. Require exactly one BAC and all KYI declaration entries, canonical 8-digit horse IDs, unique horse numbers, exact matched UKC profiles, non-sentinel data dates no later than the race date. Reject incompleteness and conflicts.
- BAC provides surface/distance/venue/date. BAC **does not provide an official going code**, so omit `track_condition_code`. Do not fill with SED post-race going.
- The exported context contains only `race` and `entrants`; it is accepted structurally by the existing `run_brdb_d4_sidecar.py`. Output receipt remains separate and is never interpreted as proof of pre-off-time publication.
- Include no odds, results, score or prediction. Entries represent **KYI declared horses**, not necessarily actual starters.
- For this fixed D3 cohort, restrict target date to >= 2026-11-02. Using a past race with later D3 post-race evidence is invalid.

## Reproduction entrypoints

```bash
python horse-racing/brdb/src/brdb_d4_paci_field.py \
  --paci /secure/paci/PACI261115.zip \
  --race-key <verified-eight-character-race-key> \
  --context /secure/d4/paci_research_context.json \
  --receipt /secure/d4/paci_source_receipt.json

python horse-racing/brdb/src/run_brdb_d4_sidecar.py \
  --full /secure/d3/d3_full_condition_evidence.json \
  --temporal /secure/d3/d3_temporal_diagnostic.json \
  --receipt /secure/d3/d3_run_receipt.json \
  --context /secure/d4/paci_research_context.json \
  --output /secure/d4/d4_paci_research_sidecar.json
```

Use a verified race key extracted from the canonical PACI BAC. The placeholder is not a runnable key and no race is asserted as executed.

## Evidence already discovered
- Canonical Drive PACI folder was directly listed during this task. Stored archives include `PACI261107.zip`, `PACI261108.zip`, `PACI261114.zip`, `PACI261115.zip`; existence alone is not bytes/SHA verification or parser E2E.
- Previously accepted D3 pins from [#2601](https://github.com/yukki0113/GPT/pull/2601): `d3_full_condition_evidence.json` SHA `705a85d4c43b369b14cbba9177f5af13ed3111f1a5031a97ee76acf51064e764`; `d3_temporal_diagnostic.json` SHA `27abb3aafabd8b5350009cf8623d43246bda70365427cc772d07e3aba4d8c8bf`; `d3_run_receipt.json` SHA `4a128dc02baf4a6ee82a1b560fa1cafb62f540cba8bed38511a97af43c3abd2e`.
- The canonical `blood_review` Drive folder inventory does not contain these three unzipped D3 result files, and keyword search for `d3_full_condition_evidence` did not return a matching Drive item. This is **not proof of absence in other allowed artifacts**. Resolve original immutable private output artifact before declaring E2E complete.

## Acceptance gate — all must pass before a non-draft merge
1. Synthetic PACI identity/date/duplicate/coverage guard tests run on **exact committed code**, with report/log and no skip.
2. Materialize one or more actually stored PACI ZIPs through approved authenticated Drive and record byte SHA, member SHA and fixed race keys.
3. Replay an actual race with **all KYI declared horses** and source-matched UKC; fail closed if a declared horse has no matching UKC.
4. Recover and verify all three pinned D3 JSON bytes; run the existing D4 sidecar twice with identical input and output SHA; account for all entered horses.
5. Independently inspect absence of future post-race data, unknown going, provenance failures, and mutation of BRDB CURRENT/frozen review/RaceNote/PWA.
6. Label result `RESEARCH_SIDECAR_ONLY`, `AS_OF_UNVERIFIED`, `prediction_safe=false`. Same-day PACI file timestamps are **not independent race off-time/source release attestation**.
7. Store non-public row-level context/results only in the approved private artifact location; GitHub gets aggregate, source/run SHA and code/tests.

## Blockers / non-goals
This PR does not claim live PACI extraction was executed or that D3 pinned files were materialized in the current runtime. D4 is non-scoring retrospective descriptive context and must not become operational Blood Review or a probability model. Timing authenticity and rate-of-success validation are separate later stages.
