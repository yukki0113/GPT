# RaceNote Forecast Reasoning / Mechanical Boundary v0.1

Status: **ACTIVE**
Date: 2026-10-01
Applies to: BTDAY-0024+ unless superseded

## 1. Purpose

A RaceNote backtest day may be completed from DAY PREP through Freeze in one user request, but the implementation must preserve a hard boundary between forecast reasoning and deterministic execution.

The one-request flow is:

~~~text
MECHANICAL PREP
  -> REASONING CHECKPOINT
  -> MECHANICAL FREEZE / VALIDATE / PUBLISH
~~~

"One request" does not mean "one mechanical prediction job."

## 2. Mechanical PREP may do

- select and persist an eligible historical date
- acquire PACI
- build full-day RaceNote Reader inputs
- enrich Analysis and RRDB under the active contracts
- enforce as-of and clean-blind firewalls
- package DAY PREP
- verify result_opened=false

PREP must not assign marks or write forecast prose.

## 3. REASONING CHECKPOINT must remain model-authored

For every race, the reasoning layer must inspect the full field and author the final forecast record content before Freeze.

It must decide and write:

- ◎ / ○ / ▲ / △1 / △2
- race_model
- mainline_cases
- single_shot_case
- mark_reason
- RRDB evidence interpretation and whether it mattered
- axis_comment
- reader_facing_reason

The ▲ selection remains an independent asymmetric rescan, not automatic rank 3.

No script may:

- rank horses from a fixed weighted formula
- choose marks from RRDB signal presence
- turn horse numbers into marks
- synthesize short comments from fixed sentence fragments
- generate decision traces from a template
- rewrite prose after it is submitted to Freeze

The prepared record must declare:

- research.authoring_mode = MODEL_RACE_BY_RACE_REASONING
- research.prose_origin = MODEL_AUTHORED_NOT_SCRIPT_GENERATED

## 4. Mechanical FREEZE may do

After complete records exist, deterministic tooling may:

- check race and horse identities against DAY PREP
- reject incomplete or duplicate five-mark sets
- reject target-day market fields
- verify RRDB contract fields
- copy market-stripped Reader inputs
- compute semantic prediction hashes
- run the forecast validator
- write canonical files
- publish the archive
- report status

It must not create or rewrite prediction meaning.

The canonical packager is:

`src/racenote_freeze_prepared_forecast.py`

The former `src/racenote_finalize_fixed_picks.py` prose-generating path is disabled.

## 5. Semantic Freeze hash

The prediction hash is semantic and excludes execution-only metadata such as:

- Git main SHA
- created_at
- frozen_at
- workflow run ID

It includes:

- race identity
- RaceNote source semantic identity
- active logic/prose contract identifiers
- prediction marks and reader-facing prediction fields
- decision trace and RRDB evidence

A technical retry with identical prepared forecast content must therefore produce the same prediction semantic hash.

## 6. Retry / immutability

Once a canonical BTDAY/date is Frozen:

- identical semantic hashes may be treated as verify-only / no-op
- different semantic hashes must not silently overwrite the existing Freeze
- any intentional replacement requires an explicit research decision outside the normal retry path

A retry is never a second prediction attempt.

## 7. Anti-template rule

Reader-facing prose is authored in the reasoning layer and checked mechanically afterward.

The validator may reject:

- repeated canned connectors across a large share of the card
- one fixed sentence skeleton with swapped names/facts
- internal research terminology in reader-facing text
- multi-paragraph or trivially short short-comments

The validator must never rewrite the prose to make it pass.

## 8. Operational target

For BTDAY-0024+ the preferred user interaction is still:

> 024を完走してください

Internally, completion means:

~~~text
T1-equivalent PREP
  -> full-field reasoning for every race
  -> complete prepared records
  -> deterministic Freeze
  -> validator
  -> canonical archive
  -> cleanup
~~~

The old T1/T2 distinction remains useful as an audit boundary, but no longer requires two separate user requests.
