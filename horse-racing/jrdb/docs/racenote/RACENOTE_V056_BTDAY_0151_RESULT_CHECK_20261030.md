# BTDAY-0151 v0.5.6 — Post-Freeze result check (2026-10-30)

Scope: 2025-02-16 Kyoto/Kokura/Tokyo, 36R, **frozen Prediction & Confidence unchanged**. This is a post-Freeze first-place evaluation, not an audited profitability / complete 3rd-place assessment.

## Provenance
- Prediction: `horse-racing/jrdb/backtests/BTDAY-0151/20250216/v056/frozen/records.json`; handoff records_sha256 `97655793fa3b3da3cee0e8a1ab300e8879022e4dbdf0db45d5d11fe9f186ad89`.
- Confidence: `.../confidence_frozen/records.json`; handoff records_sha256 `8aa27b8f172083374b4f89192df5e4f0004825ac11052c3875e17fca979c14a1`.
- Public results:
  - https://sports.yahoo.co.jp/keiba/race/list/25080106
  - https://sports.yahoo.co.jp/keiba/race/list/25100108
  - https://sports.yahoo.co.jp/keiba/race/list/25050106
- Results were consulted after both Freeze artifacts and TURN2_COMPLETE were present on main. Do not rewrite any frozen record.

## 1st-place horse numbers (R1 through R12)

| Venue | 1st-place horse numbers |
|---|---|
| 京都 | 3,5,9,11,12,13,11,14,4,6,1,3 |
| 小倉 | 2,16,14,4,8,6,8,8,17,13,13,9 |
| 東京 | 14,14,10,6,2,3,8,1,2,10,2,7 |

## Metrics

| Item | Kyoto | Kokura | Tokyo | Total |
|---|---:|---:|---:|---:|
| Races | 12 | 12 | 12 | 36 |
| ◎ winner | 4 | 3 | 5 | **12 / 36 = 33.3%** |
| 1st-place horse within all five marks | 10 | 7 | 8 | **25 / 36 = 69.4%** |

Grade A 10R: ◎ winner 3R (30.0%). Grade distribution: A10/B22/C1/Z3. Grade A per-venue winning ◎: 京都4R、小倉8R、東京12R.

## Interpretation and forward gate

- **No catastrophic collapse apparent in this one-day first-place check.**
- A grade's 30% ◎ win-rate is **not superior** to B in this sample (B 8/22=36.4%), so v056 confidence calibration remains unproven; monitor more days. Z: 1/3 ◎ wins, but excludes ordinary calibration.
- Do not claim proven parity/improvement against v0.5.5: no apples-to-apples historical baseline was validated here. This is one 36R day; statistical uncertainty substantial.
- This document does NOT prove complete horse placing, exacta/trifecta returns, ROI, or full payout profitability.
- **Forecast logic candidate GO for further controlled validation**, not unconditional FORWARD release. v056 forward PACI T1, newspaper editorial and PWA submission require their own completion/acceptance before a production forward can be declared ready.
