# RaceNote v0.4.6 / v0.5.0 Clean-Blind A/B Runbook v0.1

Status: **STAGE E RESEARCH HARNESS — NO PILOT YET**  
Date: 2026-10-06

## Boundary

Use one newly reserved BTDAY and one canonical market-blind `forecast_prep`. This runbook does not authorize opening results, final odds, popularity or payouts. It does not change the ordinary v0.4.6 BTDAY path or the current logic configuration.

Lane A uses `RaceNote-Human-Context-Reader-0.4.6-candidate` and the original clean Reader. Lane B uses `RaceNote-Human-Context-Reader-0.5.0-candidate` and **only** the derived `normal_view` files. The two lanes use the same selection id, target date, race and horse roster, PACI/Analysis preparation, RRDB contract and original Reader hashes.

## 1. Reserve and seal once

On main, reserve one unused BTDAY, commit one v0.4.6 prepare request under `backtests/requests/`, and run the existing permanent prepare workflow. Confirm DAY PREP PASS, all expected races, `market_blind=true`, `target_market_opened=false`, `result_opened=false`, and RRDB v0.3. Do not select a second date for Lane B.

Use the prepare handoff's `main_sha` as `--base-main-sha`. Initialize from the same clean Reader files:

```bash
python horse-racing/jrdb/src/racenote_ab_session.py \
  --prep-root horse-racing/jrdb/backtests/BTDAY-XXXX/forecast_prep \
  --request horse-racing/jrdb/backtests/requests/BTDAY-XXXX.json \
  --ab-root horse-racing/jrdb/backtests/BTDAY-XXXX/ab \
  --base-main-sha <forecast_prep/day_prep_handoff.json:main_sha> \
  --policy horse-racing/jrdb/docs/racenote/research-work/results/stage_c/reader_feature_policy_v0_5_candidate.json
```

The command refuses to overwrite an existing session. Commit the sealed `ab/` session and clean preparation to a shared base commit. Record that **resulting commit SHA** as the `task_base_commit` for both Cloud tasks. This task base is distinct from the preparation's `base_main_sha` recorded inside `ab_session.json`; the session cannot contain the SHA of its own future commit.

The session tree is:

```text
backtests/BTDAY-XXXX/ab/
  ab_session.json
  shared/reader_manifest.json
  v046/reader_manifest.json           # immutable reference to forecast_prep/reader
  v050/reader_manifest.json
  v050/reader/*.json                   # model-facing normal_view only
  v046/incoming/                       # temporary lane A authoring input
  v046/authored_decisions/*.json
  v046/frozen/
  v050/incoming/                       # temporary lane B authoring input
  v050/authored_decisions/*.json
  v050/frozen/
  ab_freeze_barrier.json               # absent until both lanes pass
```

The v0.5 manifest binds every normal Reader to its original filename, original file SHA-256, source semantic SHA-256 and derived normal-view SHA-256. The session does not place a provenance sidecar in the model-facing `v050/reader/`.

## 2. Start two isolated authoring tasks

Start **two fresh Cloud tasks/chat threads** from the same `task_base_commit`, on separate branches. Do not reuse a chat containing either lane's prior marks or prose.

Lane A task prompt must say:

> Work only on Lane A (`v046`) for session `<session_id>` from `<task_base_commit>`. Read the full original clean `forecast_prep/reader/` for every runner. Do not inspect the `v050` sibling branch, authored files, frozen files, marks, prose or decision traces. Do not use any sibling forecast as input. Author the v0.4.6 Decision Core for each race, save one complete venue at a time under `ab/v046`, and freeze only Lane A. Do not open target results or market. Do not merge prediction artifacts until both lane freezes exist.

Lane B task prompt must say:

> Work only on Lane B (`v050`) for session `<session_id>` from `<task_base_commit>`. Use only `ab/v050/reader/*.json` as normal model input, never its provenance or the sibling forecast. Do not inspect the `v046` sibling branch, authored files, frozen files, marks, prose or decision traces. Author an independent v0.5.0 Decision Core for each race, save one complete venue at a time under `ab/v050`, and freeze only Lane B. Do not open target results or market. Do not merge prediction artifacts until both lane freezes exist.

Both tasks must preserve the five unique roles ◎ ○ ▲ △1 △2, four mainline cases, an independent ▲ case, the final △2 boundary comparison, sparse material RRDB refs and natural reader-facing prose. A task must not copy or adapt the sibling's decisions.

For each venue, the task writes its complete Decision Core array to its own temporary `ab/<lane>/incoming/<venue>.json` and runs:

```bash
python horse-racing/jrdb/src/racenote_ab_lane.py save \
  --ab-root horse-racing/jrdb/backtests/BTDAY-XXXX/ab \
  --lane v046 \
  --decisions horse-racing/jrdb/backtests/BTDAY-XXXX/ab/v046/incoming/<venue>.json
```

Use `--lane v050` and `ab/v050/incoming/` for Lane B. The saver accepts only its own lane's incoming path, validates the complete venue card, and writes an immutable bound file to `authored_decisions/`. Commit the bound file to that lane's branch. The temporary incoming file need not be committed. Continue to the next venue.

After the full expected venue set exists on a lane branch, run:

```bash
python horse-racing/jrdb/src/racenote_ab_lane.py freeze \
  --ab-root horse-racing/jrdb/backtests/BTDAY-XXXX/ab \
  --lane v046
```

Use `v050` for Lane B. Freeze validates every Decision Core against its lane Reader, checks complete race and venue coverage, and writes the immutable lane-specific `frozen/records.json` and `frozen/lane_handoff.json`. The latter must show `FROZEN_CLEAN_BLIND` and `validator_status=PASS`. Commit the frozen files on that lane's branch.

## 3. Keep prediction branches apart

Do not merge Lane A's prediction artifacts into main before Lane B is frozen. Do not merge Lane B's prediction artifacts into main before Lane A is frozen. Do not let either authoring task read the sibling branch or artifacts. This separation is part of the experiment, not merely a directory naming convention.

After both branches independently contain complete frozen artifacts, start a **third, non-authoring integration task**. It imports the exact lane-specific `authored_decisions/` and `frozen/` files from each branch into one integration checkout of the same sealed session. It must not revise Decision Cores. The barrier revalidates the shared session, original and derived Reader hashes, every authored/frozen file, both logic ids, both complete rosters and both clean-blind statuses.

```bash
python horse-racing/jrdb/src/racenote_ab_freeze_barrier.py \
  --ab-root horse-racing/jrdb/backtests/BTDAY-XXXX/ab
```

Only this successful command writes `ab/ab_freeze_barrier.json` with `BOTH_LANES_FROZEN_CLEAN_BLIND`. Commit it with the integration artifact. If a lane is missing, tampered, mismatched, non-blind or not Validator PASS, barrier creation fails.

## 4. Post-Freeze result evaluation

Result evaluation starts only after both independent lane Freezes have been integrated
and the shared barrier exists.

Immediately before opening target results, verify the barrier against the current
bytes:

```bash
python horse-racing/jrdb/src/racenote_ab_freeze_barrier.py \
  --ab-root horse-racing/jrdb/backtests/BTDAY-XXXX/<YYYYMMDD>/ab \
  --verify-only
```

For completed 2026 JRA dates, the normal result source is the project's canonical
JRDB Raw on Google Drive. Do not begin with public Web result pages.

Generate the materialization plan:

```bash
python horse-racing/jrdb/src/jrdb_result_query_runner.py \
  --date YYYY-MM-DD \
  --plan \
  --pretty
```

For 2026 the plan resolves the daily archives:

```text
GPT/horse-racing/00_raw/SED/SEDyymmdd.zip
GPT/horse-racing/00_raw/HJC/HJCyymmdd.zip
```

Use the native Google Drive connector to resolve and materialize those exact files
into the runner's planned local paths, then query the complete day:

```bash
python horse-racing/jrdb/src/jrdb_result_query_runner.py \
  --date YYYY-MM-DD \
  --include-all-runners \
  --pretty
```

The result contract is:

- SED = horse-level finish, horse identity, final win popularity/odds;
- HJC = race-level payout authority for all eight bet types;
- SED win/place payouts = HJC cross-validation lane;
- one date query = all JRA races on that date;
- `success` or `review_required` is retained with provenance for the A/B analysis.

The A/B evaluation then joins each lane's frozen `records.json` to the parsed
results by venue + race number + horse number. At minimum compare:

- ◎ win / top-2 / top-3 performance;
- ▲ win / top-3 performance;
- winner mark distribution across ◎ ○ ▲ △1 △2 / unmarked;
- number of actual top-3 horses contained in the five marks;
- races where v0.4.6 and v0.5.0 changed ◎, ▲, or the five-horse set;
- whether those changed decisions improved or worsened the observed result.

ROI or ticket-settlement analysis is a separate metric layer. Do not substitute
betting return for the statistical prediction comparison.

Public-Web result acquisition is only a fallback when an actual canonical Drive
inventory check confirms the required JRDB Raw is unavailable, or when the requested
fact lies outside the SED/HJC result contract.

The authoritative generic result-query guide is
`docs/README_jrdb_result_query.md`; same-day settlement behavior is documented in
`docs/racenote/SAME_DAY_RESULT_SETTLEMENT_v0_1.md`.
