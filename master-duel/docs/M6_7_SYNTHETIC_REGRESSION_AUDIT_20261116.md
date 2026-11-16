# M6-7 synthetic regression audit (2026-11-16 JST)

## Scope
- Synthetic M6-7 competitive selection, full recipe archive, and rank/link tests.
- Complete existing Master Duel regression including earlier M6 suites.
- No private SQLite/ownership/card text or actual deck recipes used.
- This is **synthetic regression PASS**, not M6-7 real-data acceptance.

## Initial run (FAIL)
- Workflow: `master_duel_regression.yml`
- [Run 43795178593](https://github.com/yukki0113/GPT/actions/runs/43795178593)
- Source commit: `979e2a8744d398644583297dc13b5a2668f3a3fa`
- Focused M6-7: 9 tests executed, 1 import ERROR; full regression skipped due to preceding failure.
- Root cause: `engine_m6/recompose.py:292` contained `selected["EXTRA",cid"]` (unterminated string literal).

## Fix
- [Commit d1ebaad](https://github.com/yukki0113/GPT/commit/d1ebaad7e101c3f048bb15a842448332b5cb80f5)
- Corrected to `selected["EXTRA",cid]`. GitHub read-back verified (blob `d707d91ec59fc666858faf6d35833830393a9919`).
- CI workflow was also updated to execute focused `test_m6_7*.py` before the full regression.

## Verified rerun (PASS)
- [Run 43795285095](https://github.com/yukki0113/GPT/actions/runs/43795285095)
- Source commit: `d1ebaad7e101c3f048bb15a842448332b5cb80f5`
- Focused `test_m6_7*.py`: **19 tests, OK**.
- `engine_m6`: **239 tests, 0 skipped, PASS** (includes older M6 regression suites).
- Entire Master Duel suite: **612 tests, 1 skipped, PASS**, exit success.
- Job: `133062603297`; both focused and full-regression steps concluded success.

## Remaining acceptance boundary
- Private current HEAD / SQLite / derived index SHA checks not performed here.
- Current MD metagame `decision_policy` and individual evidence not yet built.
- Real Generation integrated Suship rebuild, cross-card audit, in-game legality, and private Drive save/read-back remain unaccepted.
- Production private HEAD and ownership database unchanged by this work.

## Evidence
The GitHub Actions run and job logs linked above are the execution evidence. This file intentionally contains only synthetic test metadata and no private user card records.
