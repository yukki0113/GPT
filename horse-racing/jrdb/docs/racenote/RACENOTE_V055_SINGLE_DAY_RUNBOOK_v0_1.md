> **2026-10-30 現行r6運用の優先案内**：新規BTDAYの標準手順は [RACENOTE_V055_R6_PIPELINE_CURRENT_RUNBOOK_20261030.md](RACENOTE_V055_R6_PIPELINE_CURRENT_RUNBOOK_20261030.md)。T2開始直後に次BTDAYのT1 Orchestratorを起動する `PIPELINE` が通常モード、`T2_ONLY` は先行起動を止めるモード。独立したLLM予想→Prediction Freeze→独立Confidence→Confidence Freeze→Batch同期→次T1の状態照合を守る。以下の旧手順・旧日付の「current」表記は当時の履歴として保持し、現行r6の起動口を置き換えない。更新前の全文は `operation-backups/20261030_pre_pipeline/RACENOTE_V055_SINGLE_DAY_RUNBOOK_v0_1.md` に退避済み。

# RaceNote v0.5.5 Candidate — Single-Day Runbook

Status: **CURRENT CANDIDATE / NEW v0.5.5 SESSIONS**  
Logic: `RaceNote-Human-Context-Reader-0.5.5-candidate`  
Revision: `v055-prediction-freeze-confidence-review-r6`

## 1. Prepare market-blind source

Use the canonical forecast preparation path with RRDB v0.5 enrichment.

Required preconditions:

```text
market_blind=true
stripped_at_input_bind=true
result_opened=false
target_market_opened=false
```

Use the existing KYI supplemental bundle and Resolver-verified RaceLap Parquet.

For normal **forward** operation, consumers resolve RaceLap through
`jrdb_race_lap_current_resolver.py`. A fresh CURRENT is validated and returned
unchanged. A stale CURRENT can advance only when the caller has already
materialized the exact canonical completed-day SED archive(s); otherwise the
resolver fails closed. The resolver never fetches JRDB or Drive data.

For normal **forward** operation, RaceLap must come from the canonical forward-current asset defined by
`RACENOTE_V055_FORWARD_EVIDENCE_OPERATION_DESIGN_v0_1.md`.

Forward T1 must not:

- fetch annual historical SED archives;
- scan a historical daily SED date range;
- rebuild RaceLap from raw history.

Before Reader seal, Forward T1 applies freshness only to RaceLap:

```text
race_lap.expected_period_to < target_date
race_lap.period_to == race_lap.expected_period_to
race_lap.period_to < target_date
```

Analysis and RRDB are maintained by their dedicated operations/threads. Forward
T1 consumes the supplied current assets but does not refresh them and does not
compare their recency/cutoff against RaceLap. Target/future-data contamination
guards remain unchanged.

The exact RaceLap Parquet SHA-256 is still bound into the v0.5.5 session, so reuse of the canonical current asset does not weaken input immutability.


RaceLap is exposed to the model through the common Reader contract, not through
consumer-side Parquet SQL. PACI recent runs retain their canonical `race_key`;
the daily RRDB/RaceNote enrichment performs one batch lookup and attaches:

```text
horses[].recent_runs[].race.race_key
  -> RaceLapReader.get_race_contexts(...)
  -> recent_runs[].race_structure
       source = JRDB_RaceLapReader_v0.1
       coverage
       lap_shape
       srb_context
       policy
       provenance
```

`lap_shape` is source-race context, not an individual-horse sectional or an
additive score. Missing RaceLap coverage is represented explicitly as
`coverage.status=NOT_FOUND`; target-date or future source rows fail closed.

## 2. Initialize the sealed Lean Model Reader

```bash
python horse-racing/jrdb/src/racenote_v055_single_day.py init \
  --prep-root <operation-root>/forecast_prep \
  --root <operation-root>/v055 \
  --base-main-sha <exact source-main SHA> \
  --evidence-bundle <operation-root>/v054_inputs/kyi_bundle.json \
  --race-lap-parquet <verified-lap-store>/race_lap.parquet
```

T2 reads the complete bound `v055-lean-model-reader-r2` for each race.

## 3. Author the prediction

Author the forecast without A/B/C:

```json
{
  "venue": "中山",
  "race_no": 1,
  "marks": [12, 2, 7, 16, 11],
  "candidate_selection": {
    "ordinary_five": [12, 2, 7, 16, 11],
    "external_challenger_horse_no": 5,
    "excluded_horse_no": 5,
    "decision": "KEEP_ORDINARY_FIVE",
    "boundary_reason": "..."
  },
  "honmei_win": {
    "evidence": "...",
    "main_risk": "..."
  },
  "shot_case": {
    "case": "..."
  },
  "rrdb_refs": [],
  "reader_facing_reason": "..."
}
```

A/B/C/Z must not be inserted into the r5 Decision Core.

The short note is editorial: write the single race-specific point most useful to the reader. Do not routinely summarize all marks.

Before saving, translate audit-layer evidence into ordinary racing language. `reader_facing_reason` must not contain internal metric/plumbing labels such as `IDM`, `RRDB`, `SRB`, `KYI`, `調教指数`, `状態指数`, Reader/Decision-Core terminology, hashes, or `None/null/NaN`. The reader should understand the note without knowing the RaceNote/JRDB internal schema.

Do not solve this by applying one reusable sentence frame to every race. A day-wide pattern such as “X is best on internal measures; at Ym the running style is preferred” is invalid even if X/Y/style differ by race. Re-read the race and choose its actual reader-useful point: winning route, principal risk, pace/position branch, ▲ appeal, uncertainty, or another supported race-specific observation.

## 4. Save prediction checkpoints

```bash
python horse-racing/jrdb/src/racenote_v055_single_day.py save \
  --root <operation-root>/v055 \
  --decisions <operation-root>/v055/incoming/<venue>.json
```

Repository-backed authored venue files remain recovery checkpoints. They are immutable once saved.

## 5. Prediction Freeze

After every expected venue is present:

```bash
python horse-racing/jrdb/src/racenote_v055_single_day.py freeze \
  --root <operation-root>/v055

python horse-racing/jrdb/src/racenote_v055_single_day.py verify-prediction \
  --root <operation-root>/v055
```

Required state:

```text
status=PREDICTION_FROZEN_CLEAN_BLIND
confidence_frozen=false
confidence_pending=true
result_opened=false
target_market_opened=false
```

From here onward, do not alter marks, Decision Core or short comments.

Do not open target results or target market.

## 6. Confidence Review

Now review the already frozen ◎ horses as a separate judgment.

Meaning:

- **A** — ◎が最有力であるだけでなく、能力差・条件適性・勝ち筋の再現性・不確実性を総合して、**このレースを買うに値するだけの事前優位性がある**。単勝軸として積極的に支持する。
- **B** — ◎は最有力だが、相手との差が小さい、主要リスクが強い、または昇級・距離替わり・初重賞などの不確実性が大きく、**予想上は◎でも実戦では見送り得る**。
- **C** — ◎は固定済みの本命だが、勝ち馬選定そのものへの確信が低い。
- **Z** — 新馬戦または障害戦。予想印は通常どおり作成するが、現行A/B/C勝ちConfidenceの評価対象外。

Z is a scope marker, not a lower confidence grade than C. For r5 it is mandatory when the sealed Reader has `race.class == 新馬`, or `race.surface/race_type == 障害`. Standard flat races must be A/B/C.

A does not mean near-certainty, and plausible upset routes do not automatically demote A to B. However, "◎が一番勝ちそう"だけではAにしない。現級・同条件で同等以上の裏付けを持つ相手がいるのに、強い未勝利勝ち・近走2着・能力印象だけでAへ上げない。逆に、明確なクラス優位や再現性の高い勝ち筋がある場合は、他に好調馬がいるだけで機械的にBへ下げない。

There is no A quota and no target grade distribution. Aが0件の日も許容するが、Aを「ほぼ確勝」や「極端な低オッズ馬」に限定しない。市場オッズはConfidence Freeze前には見ない。

Create a complete review array:

```json
[
  {
    "venue": "中山",
    "race_no": 1,
    "honmei": 12,
    "confidence": "A",
    "reason": "現級での直接実績が一段上で、主要リスクを考慮しても単勝軸として積極的に支持できる。"
  }
]
```

The `honmei` value must exactly match the frozen ◎.

Save the draft:

```bash
python horse-racing/jrdb/src/racenote_v055_single_day.py save-confidence \
  --root <operation-root>/v055 \
  --confidence <operation-root>/v055/incoming/confidence.json
```

For Z races, use a concise scope reason such as `新馬戦のため現行A/B/C勝ちConfidence集計の対象外。予想印は通常どおり有効。` or `障害戦のため現行A/B/C勝ちConfidence集計の対象外。予想印は通常どおり有効。`.

Before Confidence Freeze, `confidence_review.json` is deliberately replaceable. Re-read the frozen prediction, reconsider A/B/C boundaries, edit the incoming review and run `save-confidence` again as needed.

This is the formal pre-result reconsideration stage.

## 7. Confidence Freeze

When the review is settled:

```bash
python horse-racing/jrdb/src/racenote_v055_single_day.py freeze-confidence \
  --root <operation-root>/v055

python horse-racing/jrdb/src/racenote_v055_single_day.py verify \
  --root <operation-root>/v055
```

Final required state:

```text
Prediction:
  PREDICTION_FROZEN_CLEAN_BLIND

Confidence:
  CONFIDENCE_FROZEN_CLEAN_BLIND
  confidence_frozen=true
  confidence_meaning=HONMEI_WIN_CONFIDENCE

Both:
  result_opened=false
  target_market_opened=false
```

Only after final `verify` succeeds may result evaluation begin.

## 7.1 Completion report to the forecast execution thread

After Prediction Freeze, Confidence Freeze, and final `verify` succeed, keep the chat completion report compact.

The canonical frozen artifacts already contain the full race-by-race marks, comments, and Confidence review. Therefore, the normal completion report must summarize only:

- race / frozen counts;
- Prediction / Confidence final statuses;
- A/B/C/Z counts;
- prediction / confidence hashes;
- `result_opened=false`;
- `target_market_opened=false`;
- material technical observations, if any.

Do **not** print the full card of ◎ ○ ▲ △ △, short comments, or per-race Confidence back into the conversation after successful completion.

Only reproduce a full or partial marks table when the user explicitly asks to see it.

This is a conversation-volume control only. It does not reduce or alter any repository artifact, Freeze record, handoff, or downstream publication requirement.

## 8. Result evaluation

After result unlock report:

- total ◎ win / top2 / top3;
- winner-in-five and top3 capture;
- A/B/C/Z counts;
- A/B/C ◎ win rate, with Z excluded from every denominator;
- A/B/C ◎ single-win return when HJC payout is available, with Z excluded.

Keep Z performance only as a separate special-race reference line. Z must not be mixed into the primary A/B/C validation series or primary bankroll. Optional play is allowed only as separately accounted recreational/satellite betting when bankroll permits.

Pairwise ◎>○, IDM gaps, debut/obstacle grouping and old A5/A7-style analysis remain downstream diagnostics.

## 9. Existing r1/r2/r3/r4 sessions

Do not migrate an existing frozen r1/r2/r3/r4 session into r5 or retroactively rewrite its A/B/C records as Z. Their embedded confidence remains part of their historical Freeze.

r6 applies only to newly initialized sessions. Existing r5/r4 sessions remain reproducible under their original contracts and must not be rewritten.


## 10. Fast forward operational wrapper

For normal forward daily operation, the deterministic preparation/finalization
steps are consolidated by:

- `src/racenote_v055_forward_turn1.py`
- `src/racenote_v055_authoring_bundle.py`
- `src/racenote_v055_turn2_finalize.py`
- `.github/workflows/racenote_v055_llm_turn2_finalize.yml`

Normative operational boundary:
`RACENOTE_V055_FAST_FORWARD_OPERATION_v0_1.md`.

The authoring bundle is lossless with respect to each sealed lean Reader and
must not score, rank, filter, select marks or assign Confidence. The LLM must
still read and judge every race independently. Automation resumes only after
the LLM has authored complete Decision Core and Confidence drafts.
