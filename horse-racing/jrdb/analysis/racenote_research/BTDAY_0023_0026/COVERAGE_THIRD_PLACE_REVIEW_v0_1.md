# RaceNote Coverage研究 — 3着無印 Review v0.1

## Scope

BTDAY-0023〜0026 Discovery Set 144R。

Coverage failure:
- 110 / 144 races
- missed Top3 horses: 149
  - 1着無印: 34
  - 2着無印: 47
  - 3着無印: 68

このv0.1では、引継ぎ方針どおり **3着無印68頭を最優先**でレビューした。

比較対象は各レースの△1 / △2。
結果・最終人気は対象抽出にのみ使用し、判定は各BTDAYの
`reader_stripped/racenote_reader_*.json` に保存されたPre-Freeze情報へ戻って行った。

## Classification

- **SWAP_CANDIDATE**  
  結果を知らなくても、無印馬に△1/△2の少なくとも一方と同等以上の事前材料があり、
  5頭目付近の入替候補として扱えた。

- **COMPLETE_MISS**  
  Reader入力には馬の情報自体は存在したが、能力・近走・条件直接性・RRDB等を比較しても
  △末端より事前材料が弱く、5頭へ入れる再現可能な根拠が乏しい。

- **AMBIGUOUS**  
  入替を支持する材料はあるが、能力差・条件替わり等の反証も強く、
  事前に5頭へ入れるべきだったとまでは言えない。

## Result

- SWAP_CANDIDATE: **32 / 68**
- COMPLETE_MISS: **30 / 68**
- AMBIGUOUS: **6 / 68**

3着無印の約半数は、全く見えなかった馬ではなく
**candidate boundary（概ね5〜7番手）の入替精度**の問題だった。

一方で30頭は、Pre-Freeze情報上は△末端より弱く、
結果後に無理に拾おうとするとhindsightになる。

## Repeated SWAP patterns

### C1. 今回条件への直接性を5番手比較で軽く扱う

最頻出。

例:
- 同距離4〜7着の無印馬 vs 別距離の△
- 同距離勝ち/好走の無印馬 vs generic abilityが高い△
- 障害の今回近似距離経験 vs 別距離実績

Hierarchy研究と同じく、
**direct-condition evidence が最終候補境界で薄れる**傾向がある。

### C2. 前走着順だけでは見えないhidden strengthが候補境界に残る

主な材料:
- REPEATED_FASTEST_LAST3F
- RESULT_UNDERRATES_TIME
- REPEATED_ABOVE_CLASS_PERFORMANCE
- PACE_POSITION_AGAINST_GOOD_RUN
- HV02_Q85_Q90
- FRONT_SURVIVE_GAP05

RRDB recommendation signalそのものがなくても、
Readerにはhistory_profileのhidden strengthが見えていた馬が複数いる。

Forecastは上位5頭の理由ではこれらを使えている一方、
**6番手以下を切る局面では十分に再走査できていない可能性**がある。

### C3. △末端自身が弱い時の比較不足

SWAP_CANDIDATEには、
無印馬が絶対的に強いというより、

- △2も前走8〜16着
- △側も条件替わり
- △側のcase_forが「押さえ」「展開ひとつ」程度

というケースが多い。

つまりCoverage改善は
「穴馬をもっと拾う」ではなく、

> **△2を確定する直前に、field全体から1頭だけborderline challengerを再比較する**

方が自然。

## COMPLETE_MISS patterns

COMPLETE_MISSでは主に:
- 能力値が△末端より大きく下
- 直近大敗かつhidden positiveなし
- 今回距離への大きな条件替わり
- 新馬で事前能力/調教が下
- 障害初挑戦に近い状態

が重なる。

これらまで5頭に拾うことを目標にするとcandidate setが平坦化し、
本来の5頭選択を壊す。

## Provisional Coverage hypothesis v0.1

Forecast本体の5頭数は変えない。

5頭確定前に、analysis hypothesisとして以下を置く。

> △2確定後、全無印馬をもう一度見るのではなく、
> 「今回条件への直接実績」「前走不利/hidden strength」「△2との能力近接」
> のいずれかを持つborderline challengerだけを1頭抽出し、
> △1/△2と意味ベースで再比較する。

重要:
- score化しない
- 人気/オッズを使わない
- ▲のsingle-shot searchとは別工程
- challengerが明確に上でなければ元の5頭を維持する

## Relation to Hierarchy research

Hierarchyで見えた
- race_model consistency
- direct-condition evidence
- runs-well vs can-win

のうち、Coverageでは特に
**direct-condition evidence** が再び主要因になった。

したがってHierarchyとCoverageを別々のルールに増やすより、
Human-Context Readerの最後に

1. ◎○ hierarchy consistency
2. ▲ single-shot role integrity
3. △2 vs borderline challenger coverage check

という3つの意味ベース確認を置く方向が研究上は整合的。

## Important limitation

今回の詳細レビューは3着無印68頭が対象。

1着無印34頭、2着無印47頭については構造件数を確定済みだが、
1頭ずつのReader再比較はこのv0.1には含めない。

これは意図的で、まず馬券の◎固定trio/trifectaに直結しやすい
3着coverageを優先したため。

## Next research step

Coverage v0.1の次は2案:

1. **Coverage Retest**  
   unused BTDAYでborderline challenger仮説を結果blindに付与し、
   5頭coverageが改善するか検証。

2. **Selector v0.2**  
   Hierarchy + Coverageの知見を使い、
   decision_trace / race_model / mainline_cases / single_shot_caseを意味ベースで読むSelectorへ進む。

Forecast v0.4.2本体への変更は、Retest前には行わない。
