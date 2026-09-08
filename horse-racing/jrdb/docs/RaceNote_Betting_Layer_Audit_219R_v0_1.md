# RaceNote Betting Layer Audit — 219R v0.1

## Status

**RETROSPECTIVE BETTING-LAYER DIAGNOSTIC ONLY — NO PREDICTION OR BETTING POLICY CHANGE**

This audit keeps all 219 frozen `provisional_handoff_v0.1_unweighted` marks unchanged and re-settles the already-authoritative HJC payouts by mark role.

Purpose:

1. decompose current quinella ② into `◎-○` and `◎-▲`;
2. decompose current trio ③ into `◎○▲ / ◎○△ / ◎▲△ / ◎△△`;
3. compare the current six-ticket ◎-axis trio with a five-ticket formation that excludes only `◎△1△2`.

Audit execution:

- Issue #502 `[RACENOTE_BETTING_AUDIT_REQUEST] 219-race role decomposition`
- workflow run `34198184883`
- artifact `racenote-betting-audit-34198184883`
- artifact id `10044851757`
- artifact digest `sha256:c9f9722681855f2bb89a5e7de5ed605c76c302fcd5b487f3a037dff438e8abd5`
- audit tool: `src/audit_racenote_betting_layer.py`

The total settlement checksums reproduce the existing 219R reference:

- quinella current 2-ticket: 43,800円 -> 35,230円 = 80.43%
- trio current 6-ticket: 131,400円 -> 105,720円 = 80.46%

## 1. Quinella role decomposition

| Ticket role | Investment | Payout | Hit races | Hit rate | Return rate |
|---|---:|---:|---:|---:|---:|
| ◎-○ | 21,900円 | 18,670円 | 29/219 | 13.24% | **85.25%** |
| ◎-▲ | 21,900円 | 16,560円 | 17/219 | 7.76% | **75.62%** |
| Current 2-ticket total | 43,800円 | 35,230円 | 46/219 | 21.00% | **80.43%** |

The hypothesis that `▲` is already the main economic engine of the quinella is **not supported overall**. `◎-○` has the higher historical return and more hits.

However, `◎-▲` has a clear higher-payout-per-hit character:

- ◎-○ average payout per hit: about **644円**; median **490円**
- ◎-▲ average payout per hit: about **974円**; median **830円**

Thus `▲` is not formally a value slot, but it already behaves more like a lower-frequency / higher-payout opponent than `○`.

Payout concentration is also stronger for `◎-▲`:

- top 5 ◎-▲ hits produced about 51.2% of all ◎-▲ payout;
- top 5 ◎-○ hits produced about 40.3% of all ◎-○ payout.

Largest ◎-▲ payout examples:

- 2025-05-04 新潟11R: 2,970円
- 2025-05-25 新潟1R: 1,750円
- 2025-11-16 京都2R: 1,620円
- 2025-05-24 東京8R: 1,090円
- 2025-05-25 新潟2R: 1,050円

### Quinella block stability

| Blind block | Races | ◎-○ | ◎-▲ |
|---|---:|---:|---:|
| 2025-05-04 | 36 | 103.33% | **143.33%** |
| 2025-05-24/25 | 72 | 59.58% | **75.42%** |
| 2025-08-23/24 | 39 | **81.03%** | 9.23% |
| 2025-11-15/16 | 72 | **104.17%** | 77.92% |

The role advantage reverses by block. Therefore `▲ = forced longshot/value horse` is not justified from these 219 races.

## 2. Trio role decomposition

The current six-ticket trio consists of:

- `◎○▲`: 1 ticket/race
- `◎○△`: 2 tickets/race
- `◎▲△`: 2 tickets/race
- `◎△△`: 1 ticket/race

| Role group | Tickets/race | Investment | Payout | Hit races | Return rate |
|---|---:|---:|---:|---:|---:|
| ◎○▲ | 1 | 21,900円 | 18,450円 | 17 | **84.25%** |
| ◎○△ | 2 | 43,800円 | 37,150円 | 24 | **84.82%** |
| ◎▲△ | 2 | 43,800円 | 32,920円 | 16 | **75.16%** |
| ◎△△ | 1 | 21,900円 | 17,200円 | 4 | **78.54%** |
| Current 6-ticket total | 6 | 131,400円 | 105,720円 | 61 | **80.46%** |

The two strongest historical role groups are `◎○△` and `◎○▲`, both around 84-85% return. `◎▲△` is weaker, and `◎△△` is extremely low frequency.

`◎△△` hit only 4/219 races, with payouts:

- 2025-05-25 京都9R: 5,430円
- 2025-08-23 札幌4R: 4,540円
- 2025-05-04 京都6R: 4,520円
- 2025-05-25 新潟3R: 2,710円

The sixth ticket therefore behaves like a sparse tail-coverage ticket rather than a stable core ticket.

## 3. Six-ticket flow vs five-ticket formation

Five-ticket candidate:

```text
◎ -> ○▲ -> ○▲△1△2
```

Equivalently, keep:

- ◎○▲
- ◎○△1
- ◎○△2
- ◎▲△1
- ◎▲△2

and remove only:

- ◎△1△2

### 219R comparison

| Trio policy | Tickets/race | Investment | Payout | Hit races | Return rate |
|---|---:|---:|---:|---:|---:|
| Current ◎ axis flow | 6 | 131,400円 | 105,720円 | 61/219 | **80.46%** |
| ○ or ▲ required formation | 5 | 109,500円 | 88,520円 | 57/219 | **80.84%** |

Removing `◎△△`:

- saves 21,900円 investment;
- loses 17,200円 payout;
- loses 4 hit races;
- improves total return only **+0.38 percentage points**.

The incremental historical ROI of the sixth `◎△△` ticket itself is **78.54%**.

Therefore the five-ticket formation is marginally better on the pooled 219R, but not by enough to declare it superior.

### Block stability

| Blind block | Races | 6-ticket | 5-ticket | ◎△△ incremental ROI |
|---|---:|---:|---:|---:|
| 2025-05-04 | 36 | **78.24%** | 68.78% | 125.56% |
| 2025-05-24/25 | 72 | **74.63%** | 66.94% | 113.06% |
| 2025-08-23/24 | 39 | **104.02%** | 101.54% | 116.41% |
| 2025-11-15/16 | 72 | 74.63% | **89.56%** | 0.00% |

This instability is decisive for interpretation: the pooled +0.38pt improvement of the five-ticket formation is caused by block mixing. In the first three historical blocks the sixth ticket helped; in the November block it never hit and was pure cost.

## 4. Interpretation for prediction-vs-betting design

### ▲

Current `▲` must not be redefined as “always choose a longshot”. The data says:

- it hits less often than ○;
- when it hits, the payout is materially larger;
- its block-level ROI is unstable;
- current qualitative selection already occasionally promotes ability-vs-market disagreement horses into ▲/△.

A cleaner v0.2 candidate is to preserve pure prediction marks and create a separate **value/disagreement opponent** in the betting layer, rather than forcing `▲` itself to be a longshot.

### Trio

The historical data does not support an immediate switch from six to five tickets. The five-ticket formation is economically almost tied with the current flow and loses four large tail hits.

The correct next test is prospective A/B:

- Policy A: current six-ticket ◎-axis flow
- Policy B: five-ticket `◎ -> ○▲ -> ○▲△1△2`

Freeze both before HJC on the next untouched sample.

## 5. Recommended next experiment

Do not rewrite the 219R history or promote a retrospective winner.

For the next untouched blind block:

1. keep prediction v0.1 as control;
2. if a distance-aware prediction candidate is introduced, freeze it separately as v0.2 candidate;
3. for each prediction set, freeze both trio policies A/B;
4. retain current quinella `◎-○ / ◎-▲` as baseline;
5. optionally define one preregistered `value/disagreement opponent` candidate without forcing market rank or odds thresholds after seeing results;
6. evaluate axis accuracy and opponent capture separately from headline return.

Useful diagnostics going forward:

- ◎ win / top2 / top3 capture;
- ○ vs ▲ top2 capture and payout contribution;
- ability-vs-market disagreement of opponent candidates;
- actual 2nd/3rd horse capture by ○/▲/△;
- axis-correct / opponent-miss races;
- six-ticket vs five-ticket incremental ROI by independent block.
