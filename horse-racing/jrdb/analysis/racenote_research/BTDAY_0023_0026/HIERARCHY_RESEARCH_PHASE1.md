# RaceNote Hierarchy Research Phase 1 — BTDAY-0023〜0026

## Scope
BTDAY-0023〜0026、144R。

Hierarchy failure は
`winner_in_five = true && main_won = false`
とする。

再集計の結果:
- 勝ち馬5頭内: 110/144
- ◎勝: 46/144
- Hierarchy failure: **64R**

以前の会話で54Rとした記載は誤り。64Rを正とする。

## Winner mark distribution
| winner mark | count |
|---|---:|
| ○ | 23 |
| ▲ | 11 |
| △1 | 18 |
| △2 | 12 |
| total | 64 |

## By day
| BTDAY | hierarchy failure |
|---|---:|
| 0023 | 15 |
| 0024 | 15 |
| 0025 | 21 |
| 0026 | 13 |

0025が最多。特に東京9R、小倉7R、京都5R。

## Where did ◎ finish in hierarchy failures?
| ◎ finish | count |
|---|---:|
| 2nd | 17 |
| 3rd | 9 |
| outside Top3 | 38 |

64R中26Rは◎もTop3内。
一方38Rは勝ち馬を5頭内に持ちながら◎自体はTop3外。

## Pre-race structured comparison: ◎ vs actual winner
reader_stripped の事前情報だけを比較。

直近着順を両馬で比較可能だった60R:
- actual winner had better recent finish: **8**
- same recent finish: **11**
- actual winner had worse recent finish: **41**

したがって hierarchy failure の **68.3% (41/60)** は、
実際の勝ち馬の方が直近着順では悪いケース。

64R全体:
- actual winner IDM > ◎: **7**
- actual winner total_index > ◎: **6**
- actual winner training_index > ◎: **12**
- winnerだけRRDB recommendation signalあり: **8**
- ◎だけRRDB recommendation signalあり: **7**
- actual winnerの直近走に不利・ロス・展開厳等の明示的noteあり: **29**

### Interpretation
Hierarchy failure の主因は
「指数上明らかに上の馬を見落としていた」
ではない。

むしろ多くは:
1. ◎が直近着順・IDM・総合指数で素直に優位
2. 勝ち馬は○▲△として候補には拾えている
3. 勝ち馬側に前走不利、条件替わり、展開変化、RRDB hidden-strength 等の逆転シナリオがある
4. その逆転シナリオを「候補に残す」ことには成功したが、◎を上回るまで強く評価しなかった

という構造。

## Failure types

### H1 — Mainline near-tie
主に○勝ち23R。
◎と○の双方に十分な好走根拠があり、◎固定まで差が大きくない。

Examples:
- 2026-05-03 京都9R: ◎サンライズバレット vs ○レヴァンテシチー
- 2026-02-01 京都3R: ◎パラダイスフェイス vs ○アスクチャンスマン
- 2026-02-15 東京5R: ◎サムシングスイート vs ○ナックホワイト
- 2026-01-24 小倉10R: ◎サラトガチップス vs ○キングスコール

Research implication:
「○が勝った=◎選定ミス」と一律に扱わず、
◎○がほぼ同格だったかを分離する必要がある。

### H2 — Hidden-strength / counterargument win
主に▲勝ち11R。
通常本線では下だが、別線として拾った逆転シナリオが実現。

Examples:
- 2026-05-03 京都1R ▲ピカラ — TIME_CLASS_PLUS1
- 2026-05-03 新潟5R ▲ワールドブレイヴ — REAR_HIGH_LAST3F90
- 2026-02-01 小倉12R ▲セイウンデセオ — REAR_HIGH_LAST3F90
- 2026-02-15 東京8R ▲エフォートレス — REAR_HIGH_LAST3F90
- 2026-01-24 京都2R ▲リアルアルバ — 前走大敗からの条件/展開変化

Research implication:
▲が勝ったこと自体は current ▲ concept と矛盾しない。
▲を◎へ吸収すると single-shot の役割を壊す可能性がある。
必要なのは「▲が◎を負かす確率が高いレース」の識別。

### H3 — Lower-mainline contextual reversal
△1 18R + △2 12R = 30R。
勝ち馬は候補5頭には入ったが、本線序列では低かった。

Typical patterns:
- 距離短縮/延長
- 初ダート・条件替わり
- 前走不利/ロス
- 調教上昇
- 前走着順より内容が良い
- 先行/差しの展開反転

Examples:
- 2026-02-01 京都1R △2グラシアムヘール — 初ダート
- 2026-02-01 小倉7R △2キャットテイル — 1700m短縮
- 2026-02-15 東京11R △2リアライズシリウス — スロー時の先行残り
- 2026-01-24 小倉7R △2スズカミエール — 前走不利+調教上昇

Research implication:
5頭候補生成は機能している。
序列改善では「直近着順/指数の優位」を打ち消せる contextual reversal の強さをどう読むかが焦点。

## Important negative finding
Hierarchyを改善するために
「勝ち馬側のIDM/総合指数をもっと重視する」
という方向は支持されない。

実際の勝ち馬が◎より:
- IDM上は 7/64
- total_index上は 6/64

しかない。

単純な指数順位へ寄せると、むしろ current Reader の強みを失う可能性がある。

## Provisional conclusion
現時点ではForecastロジック自体をすぐ変更しない。

優先研究は:
1. **◎と○の差が本当に十分だったか** — H1
2. **▲/△のcontextual reversalをどこまで強く扱うべきか** — H2/H3
3. **◎に自信を持って固定できるレース vs 5頭は合うが◎は固定しにくいレース** の区別

この③が Race Selector の `axis_confidence` 再設計に直結する。

## Next drill-down
64Rを以下に再分類する:
- CLEAR_MAIN_ERROR: 事前材料を再読しても勝ち馬を◎より上げる合理的余地が大きい
- NEAR_TIE: ◎/勝ち馬の差が小さく順序誤差とみなせる
- CONTEXTUAL_REVERSAL: 勝ち馬の逆転条件は読めていたが発生確率を低く置いた
- IRREDUCIBLE_VARIANCE: 事前材料から序列反転を強く予見しにくい

この分類は結果を知った事後分析なので、Selectorラベルとは分離する。
