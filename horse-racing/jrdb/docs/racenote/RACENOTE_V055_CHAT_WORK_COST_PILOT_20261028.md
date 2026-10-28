# RaceNote v0.5.5 r6 — Chat vs Work small pilot (2026-10-28)

## Goal
Maximize independently reasoned, CLEAN BLIND LLM predictions per user request **subject to shared Work/Codex allowance**. This is a comparison plan, not evidence that Work can finish 36R.

## Fixed baseline
- BTDAY-0136 is 36 races. Three independent LLM-authored race records are persisted on PR #2225 branch only: 中山01, 中山07, 阪神09; 33 remain.
- Read-only artifact delivery and SHA integrity verified for 36R.
- One-race core validation and three-record checkpoint read back tests passed. No Prediction Freeze or Confidence Freeze.
- Total reader raw LLM input previously estimated ~1.92M tokenizer proxy tokens. ZIP size must not be used as LLM token cost.
- Regular Chat Work/Codex shared-credit consumption: zero attributable to this Chat test, but model tokens/time not directly metered here.
- Work pilot consumption: NOT MEASURED. This chat cannot operate Work mode or inspect the user's account's allowance.

## Pilot plan: one new, previously unmarked race
1. In Settings > Usage (or desktop Settings > Usage & billing), record available included Work/Codex allowance before start. Avoid purchasing credits.
2. Select a **single unsolved race** from BTDAY-0136; do not reuse the three completed predictions.
3. Start a Work task with a strict **one-race cap** and the existing read-only race ZIP / authoritative Reader. Do not read results, payouts, final odds or target market. Do not write canonical BTDAY artifacts.
4. The Work LLM reads every runner and writes exactly one valid r6 prediction Decision Core with all original evidence. It may only commit a new verified immutable `llm_checkpoints/BTDAY-0136/prediction/<venue>_<NN>.json` to the PR branch, never to main.
5. Verify full single-race canonical validator PASS; independently verify commit SHA. No Confidence yet; no automated mark or confidence generation.
6. Record remaining Work/Codex allowance after the task (allow the dashboard to refresh). Record model/reasoning, start/end, credit delta, attempts, success and output quality.
7. Stop immediately if the race is incomplete, evidence is insufficient, unauthorized data is accessed, or unexpectedly high allowance is consumed. No automatic 12R or 36R rollout.

## Acceptance
- All runners explicitly considered, r6 schema and validator PASS, unique non-template rationale.
- GitHub immutable checkpoint independently visible; no modification to T1, Freeze, main.
- One user instruction completed one race without user handholding.
- Measured allowance delta within user-approved envelope (to be determined from their actual usage display).
- Zero added API charges or purchased credits.

## Next comparison
Only if 1R Work passes and allowance use is acceptable, test a second *different* pending race in regular Chat using the same evidence criteria and measure steps, then consider 3R in Work. Extrapolation to 36R must carry uncertainty; processing time and model token cost are not linear or guaranteed.

## Work prompt
Perform exactly ONE new RaceNote v0.5.5 r6 CLEAN BLIND Prediction race from BTDAY-0136 on branch feat/racenote-v055-racezip-delivery-20261028. Exclude completed 中山01, 中山07, 阪神09. Read every runner from the existing T1 Reader/one-race ZIP, reason independently, and produce a complete r6 Decision Core. Run the existing canonical validator before saving an immutable checkpoint under horse-racing/jrdb/llm_checkpoints/BTDAY-0136/prediction; verify the commit and report its SHA. No automatic scoring/mark selection; no result, odds or target-market access; no canonical BTDAY root or main modifications; no freeze. Stop after one valid race. State model/reasoning and resulting Work/Codex usage if observable; otherwise report it as unavailable.
