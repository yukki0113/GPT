# RaceNote v0.4.6 vs v0.5.0 Clean-Blind A/B — BTDAY-0049 / 0050 Result Review

Date of review: 2026-10-07

## Scope

Formal same-day clean-blind A/B cohort:

- BTDAY-0049: 2026-03-22 / 36R
- BTDAY-0050: 2026-09-05 / 36R
- total: 72R per lane

Lane A:
- `RaceNote-Human-Context-Reader-0.4.6-candidate`

Lane B:
- `RaceNote-Human-Context-Reader-0.5.0-candidate`

Both days passed the Stage E shared Freeze barrier before result access.

Result authority:
- SED = finish / horse result
- HJC = payout
- SED/HJC win/place cross-validation mismatch: 0 races on both days

Raw SHA-256:
- SED260322.zip: `6dafd60a7d7a410d1507e94841de97b8a91a3822d75073189b8d334b64333c7f`
- HJC260322.zip: `485ea31ca68a9bb573050e5cbaf6189a8256c54d037863106ce689347579c460`
- SED260905.zip: `24b4a42f1402f672fdce6121a0284ec159d05417426506f32565fc2a46531493`
- HJC260905.zip: `f339cf1573ed27261ade9943da64137414597b2587b534f95e932af2922d0e90`

## Primary forecast metrics

| BTDAY | lane | ◎ win | ◎ top2 | ◎ top3 | winner in five | all Top3 in five | marked Top3 total |
|---|---|---:|---:|---:|---:|---:|---:|
| 0049 | v0.4.6 | 9/36 25.0% | 16/36 44.4% | 21/36 58.3% | 27/36 75.0% | 10/36 27.8% | 77 |
| 0049 | v0.5.0 | 8/36 22.2% | 15/36 41.7% | 22/36 61.1% | 26/36 72.2% | 8/36 22.2% | 74 |
| 0050 | v0.4.6 | 9/36 25.0% | 15/36 41.7% | 24/36 66.7% | 27/36 75.0% | 14/36 38.9% | 80 |
| 0050 | v0.5.0 | 7/36 19.4% | 13/36 36.1% | 23/36 63.9% | 25/36 69.4% | 11/36 30.6% | 79 |
| combined | v0.4.6 | 18/72 25.0% | 31/72 43.1% | 45/72 62.5% | 54/72 75.0% | 24/72 33.3% | 157 |
| combined | v0.5.0 | 15/72 20.8% | 28/72 38.9% | 45/72 62.5% | 51/72 70.8% | 19/72 26.4% | 153 |

## Same-day paired change

The Reader change materially changed the authored prediction.

- same ◎: 58/72 = 80.6%
- same five-horse set: 14/72 = 19.4%
- exact same five-mark order: 2/72 = 2.8%
- set overlap:
  - 5/5 same: 14 races
  - 4/5 same: 44 races
  - 3/5 same: 14 races
  - mean overlap: 4.0 / 5

Winner-in-five paired transitions:
- v0.5.0 gain over v0.4.6: 5 races
- v0.5.0 loss vs v0.4.6: 8 races
- net: -3 races

◎-win paired transitions:
- v0.5.0 newly correct: 1 race
- v0.5.0 changed away from a v0.4.6 winning ◎: 4 races
- net: -3 wins

All-Top3-in-five transitions:
- v0.5.0 gain: 3 races
- v0.5.0 loss: 8 races
- net: -5 races

Marked Top3 count change:
- v0.5.0 higher: 12 races
- v0.5.0 lower: 15 races
- same: 45 races
- net marked Top3: 157 -> 153

## Winner role distribution

Combined 72R:

| role | v0.4.6 winner count | v0.5.0 winner count |
|---|---:|---:|
| ◎ | 18 | 15 |
| ○ | 16 | 14 |
| ▲ | 4 | 5 |
| △1 | 5 | 11 |
| △2 | 11 | 6 |

v0.5.0 shifted winning horses away from ◎/○/△2 and toward △1/▲ in this sample.

## Betting diagnostics

100 yen per ticket.

| bet | v0.4.6 ROI | v0.4.6 hits | v0.5.0 ROI | v0.5.0 hits |
|---|---:|---:|---:|---:|
| ◎ win | 60.7% | 18 | 44.3% | 15 |
| ◎○ quinella | 56.0% | 8 | 46.0% | 6 |
| ◎▲ quinella | 34.4% | 3 | 170.3% | 3 |
| ◎→○ exacta | 83.2% | 6 | 24.3% | 2 |
| ◎→▲ exacta | 18.2% | 1 | 263.1% | 3 |
| ◎-key trio 6 | 130.2% | 21 | 75.2% | 20 |
| ◎ first-fixed trifecta 12 | 43.4% | 8 | 42.2% | 5 |
| five-horse trio box 10 | 115.4% | 27 | 86.1% | 23 |

### Day split

BTDAY-0049:
- v0.5.0 ◎▲ quinella ROI 340.6%
- v0.5.0 ◎→▲ exacta ROI 526.1%
- v0.4.6 ◎-key trio 6 ROI 171.2%
- v0.4.6 five-horse trio box 10 ROI 131.4%

BTDAY-0050:
- v0.5.0 ◎▲ quinella / ◎→▲ exacta: 0 hits
- v0.4.6 ◎→○ exacta ROI 103.3%
- v0.5.0 five-horse trio box 10 ROI 129.5%

The positive v0.5.0 ◎▲ return is highly payout-concentrated. In BTDAY-0049 中山11R:
- v0.5.0 marks: ◎10 / ○14 / ▲11 / △12 / △7
- result: 10 -> 11
- ◎▲ quinella payout: 8,450 yen
- ◎→▲ exacta payout: 13,990 yen

This single race accounts for about 69% of the combined v0.5.0 ◎▲ quinella return and about 74% of its ◎→▲ exacta return. BTDAY-0050 produced no hit in either lane.

## Key paired cases

### Positive v0.5.0 case — BTDAY-0049 中山11R

v0.4.6:
- ◎14 / ○10 / ▲7 / △3 / △12

v0.5.0:
- ◎10 / ○14 / ▲11 / △12 / △7

Result:
- 1st #10 ドラゴンウェルズ
- 2nd #11 ムーヴ
- 3rd #4 ユキマル

v0.5.0 promoted #10 to ◎ and introduced #11 as the independent ▲ based on the emphasized late-speed ceiling. This was a real useful Reader-induced reordering and generated the large ◎→▲ payout.

### Negative axis changes

v0.5.0 changed away from a v0.4.6 winning ◎ in four races:

- BTDAY-0049 中山3R: v0.4.6 ◎12 winner -> v0.5.0 ◎8
- BTDAY-0049 中山8R: v0.4.6 ◎16 winner -> v0.5.0 ◎10
- BTDAY-0050 札幌7R: v0.4.6 ◎6 winner -> v0.5.0 ◎8
- BTDAY-0050 札幌9R: v0.4.6 ◎6 winner -> v0.5.0 ◎12

v0.5.0 created one reverse gain:
- BTDAY-0049 中山11R: v0.4.6 ◎14 -> v0.5.0 ◎10 winner

This 1 gain / 4 loss balance explains the combined ◎ win decline.

## Interpretation

Current same-day evidence does **not** support promoting v0.5.0 as a better general Reader.

Across 72 paired races:
- ◎ win: 25.0% -> 20.8%
- ◎ top3: unchanged at 62.5%
- winner in five: 75.0% -> 70.8%
- all Top3 in five: 33.3% -> 26.4%

The Reader reduction is therefore not merely cosmetic: it changes membership and ordering frequently, but the average change has so far been neutral-to-negative on primary forecast quality.

There is one interesting positive signal: v0.5.0 produced a rare high-value ◎▲ restructuring at BTDAY-0049 中山11R. Because this effect disappeared completely on BTDAY-0050 and is highly concentrated in one payout, it should be treated as a case study rather than evidence of stable ROI improvement.

The next research question should not be threshold tuning. It should inspect the 13 winner-in-five flip races (5 gains / 8 losses), especially the four races where v0.5.0 demoted a winning v0.4.6 ◎, and identify which v0.4.6 evidence tier was hidden or de-emphasized. That directly tests whether the v0.5.0 REDUNDANT_HIDDEN policy is suppressing genuinely useful corroborating evidence.

## Decision

- Keep v0.5.0 as research candidate only.
- Do not promote it over v0.4.6 from these 72 races.
- Do not tune betting policy from the ◎▲ ROI spike.
- Continue clean same-day A/B with the current Reader contracts for additional BTDAYs.
- Next diagnostic: classify paired gain/loss races by v0.5.0 Reader feature tier / hidden evidence source.
