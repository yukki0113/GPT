# RaceNote Portfolio Odds Query v0.1 — Source and Interface

## Verified current source boundary (2026-10-21)

- Current `jrdb_raw.py` PACI KYI parser exposes `base_win_odds` and `base_place_odds`. These are pre-race base estimates, **not closing odds**.
- PACI/BAC provides race identification. The current parser does **not** expose arbitrary quinella/exacta odds.
- Canonical JRDB HJC result query contains **winning combinations only**; payout / 100 may be used as effective closing odds for a **winning** combination, but cannot price losing tickets.
- Therefore **neither current PACI nor HJC alone can provide the five requested numbers for every A race**. Do not silently synthesize missing prices or scrape public race results.

## Implemented query

`src/racenote_portfolio_odds_query.py` resolves, from a validated external odds-snapshot JSON:

- `win_1` (horse 1 WIN)
- `quinella_1_2`, `quinella_1_3` (unordered)
- `exacta_1_2`, `exacta_1_3` (ordered)

Input: `--race-key YYYYMMDD-venue-R --horse1 N --horse2 N --horse3 N --odds-json PATH`.

Output: `racenote-portfolio-odds-v0.1`; `success` (all five), `partial` (missing or invalid values), `not_found` (race absent), `error` (invalid input). CLI exit codes respectively 0, 3, 4, 2.

The snapshot is **read-only**. The module does not fetch remote websites, rewrite Prediction or Confidence, apply stakes, or calculate ROI.

### Example source snapshot

The numbers below are **illustrative, not real prices**.

```json
{
  "schema_version": "racenote-odds-snapshot-v0.1",
  "source": {"provider": "verified_market_snapshot", "as_of": "2025-04-26T15:00:00+09:00", "kind": "closing_or_latest"},
  "races": [
    {
      "race_key": "20250426-京都-10",
      "win": {"8": 3.4},
      "quinella": {"5-8": 12.8, "6-8": 21.6},
      "exacta": {"8>5": 18.2, "8>6": 27.5}
    }
  ]
}
```

```bash
python horse-racing/jrdb/src/racenote_portfolio_odds_query.py \
  --odds-json /path/to/verified_snapshot.json \
  --race-key 20250426-京都-10 --horse1 8 --horse2 5 --horse3 6 --pretty
```

## Remaining acquisition integration (not yet solved)

A market-odds authority for **all combinations including losers**, preserving race identity and source timestamp, must be identified/approved and converted into the snapshot contract. This is a blocking data-source requirement for full historical Portfolio v0.1 evaluation of BTDAY-0120/0121. Do not mislabel the query implementation as end-to-end market acquisition.

Once the source is confirmed, attach a narrow read-only adapter producing this snapshot, independently from the Portfolio evaluator. Regime L requires exacta; the generic five-field output is always supplied, with missing legs explicitly represented as null.
