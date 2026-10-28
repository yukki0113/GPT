# RaceNote r6 Confidence checkpoint operating contract

The predictive LLM must finish the entire independently authored Prediction set; the existing canonical Prediction Freeze workflow must commit `frozen/day_handoff.json` and `frozen/records.json` to **main** before Confidence begins.

This candidate CLI deliberately refuses all Confidence activity on a T1-only root, including status and next. It calls the existing `verify_freeze` before presenting the frozen honmei. It never assigns A/B/C/Z or authors reasons.

Usage after independently verifying the committed Prediction Freeze on main:

```bash
ROOT=horse-racing/jrdb/backtests/BTDAY-0136/20250302/v055
STORE=horse-racing/jrdb/llm_checkpoints/BTDAY-0136/confidence
CLI=horse-racing/jrdb/src/racenote_v055_r6_confidence_cli.py
python "$CLI" --root "$ROOT" --store "$STORE" next
# LLM independently examines the frozen honmei and full clean-blind reader;
# it authors exactly {venue,race_no,honmei,confidence,reason}.
python "$CLI" --root "$ROOT" --store "$STORE" save --draft /tmp/llm_confidence_one_race.json
python "$CLI" --root "$ROOT" --store "$STORE" status
python "$CLI" --root "$ROOT" --store "$STORE" finalize --output /tmp/BTDAY0136_llm_confidence.json
```

The finalized output must pass the existing `racenote_v055_r6_submit_gate.py --phase confidence`. Commit **only** the approved `incoming/llm_confidence.json` file to main through the existing authenticated GitHub connector. The permanent Confidence Freeze workflow must persist a verified `confidence_frozen/day_handoff.json` and `turn2_summary.json`. Do not report TURN2_COMPLETE without checking committed main.

Checkpoints are immutable and outside canonical BTDay root. An existing valid checkpoint may be reused only when identical. The CLI does not push or alter main. It cannot be exercised against BTDAY-0136's real Confidence state until all 36 predictions have been authored and Prediction Freeze committed; no synthetic Confidence judgments are permitted.

Tested in this PR: mandatory negative T1-only boundary. **Not yet tested:** true frozen-positive Confidence authoring, full-day assembly and permanent Freeze end to end.

No market, odds, results, payouts, heuristic grades or automatic prediction generation.
