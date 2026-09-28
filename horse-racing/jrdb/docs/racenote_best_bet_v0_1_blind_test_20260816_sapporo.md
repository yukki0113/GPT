# RaceNote Best Bet v0.1 Blind Test — 2026-08-16 Sapporo

Status: FROZEN BEFORE RESULT LOOKUP
Scope: Sapporo 1R-12R
Research layer: RaceNote-Best-Bet-Research-v0.1
Purpose: test ◎ only, defined as "the horse the user most wants to buy in this race."

## Blind boundary
Not used before freeze:
- results
- current odds / market
- current JRDB consensus
- Training Edge
- EdgeDB match
- RL index

## Frozen ◎ selections

### 1R — 3yo Maiden, Dirt 1700m
◎ 5 ルージュリヴィエラ
Decision: BALANCED_EVIDENCE

直近2走を連続2着と、未勝利では現状の再現性を最も買いやすい。Abilityは絶対値で抜けてはいないが、TrendはSUPPORTIVE、JRDB状態もSUPPORTIVEで、近走内容と今回条件が同じ方向を向いている。最上位能力候補との差より、今この条件で買える材料の揃い方を優先して◎。

### 2R — 2yo Maiden, Turf 1200m
◎ 3 タイフーンナイン
Decision: ABILITY_OVERRIDE

新馬2着、続く未勝利も2着で、少ないキャリアながら今回の比較ではAbilityと着順の再現性が一段上。Trend材料はまだ薄く強い後押しにはできないが、ここは局所Trendで逆転させるだけの材料もなく、素直に地力・近況を優先する。

### 3R — 3yo+ 1-win Class, Turf 1800m
◎ 10 クリスレジーナ
Decision: ABILITY_OVERRIDE

1勝クラスの特別戦を含め2着・3着を繰り返し、今回メンバーではAbilityの土台が最も高い。TrendはMIXEDで決め手にはしづらいが、同クラスで積み上げた実績を覆すほどの逆風とは見ない。近走の3着も含め、ここでは地力を素直に買う。

### 4R — 3yo Maiden, Dirt 1700m
◎ 8 アルジェンタム
Decision: CONTEXTUAL_EDGE

Abilityの中央値だけなら上位にさらに安定した馬がいるが、直近3着、過去にも2着があり、TrendとJRDB状態がともにSUPPORTIVE。大敗歴があるぶん安定一辺倒ではないものの、未勝利戦では直近の上向きと今回条件への追い風を買いたい。能力差が小さい組なら、今回はこの馬を◎。

### 5R — 2yo Newcomer, Turf 1800m
◎ 11 レジームチェンジ
Decision: MIXED_RACE_BEST_AVAILABLE

新馬戦で全馬に過去走Abilityがなく、現行RaceNoteでは通常戦と同じ比較ができない。利用可能な材料の中ではJRDB状態が上昇で、騎手の札幌芝に関する母集団成績も強く、相対的には買う理由を作りやすい。ただしこれは新馬専用ロジック未整備下の暫定◎で、通常レースと同じ信頼度では扱わない。

### 6R — 3yo+ 1-win Class, Dirt 1000m
◎ 10 ヨドノゴールド
Decision: BALANCED_EVIDENCE

直近2着で、Abilityも今回の上位グループ。TrendはSUPPORTIVEで、近走の実戦内容と条件傾向が噛み合う。RaceReviewにはfragile要素が残るが、同程度の能力馬との比較なら直近の2着を重く見て◎。

### 7R — 3yo Maiden, Turf 2000m
◎ 16 ミナヅキ
Decision: ABILITY_OVERRIDE

直近2着、その前も3着で、今回の未勝利組ではAbilityと近走の再現性が最も素直。Trendは強い後押しがないものの、他のTrend好転馬には直近大敗やAbility面の不安がある。ここは傾向より、何度も勝ち負け圏まで来ている地力を優先する。

### 8R — 3yo+ 1-win Class, Dirt 1700m
◎ 4 グレイスフルマーチ
Decision: CONTEXTUAL_EDGE

直近2走を連続2着、最新Abilityも52まで上がっており、今の状態なら1勝クラス突破に最も近いと見る。過去の大敗があるためRaceReviewはfragileだが、JRDB状態はSUPPORTIVE。過去全体のブレより直近の連続好走を重視して◎。

### 9R — Otaru Tokubetsu, 1-win Class, Turf 1200m
◎ 3 エコロハート
Decision: TREND_ALIGNED

前走2着で最新Ability48、今回の上位馬との能力差は大きくない。その中でTrendがSUPPORTIVEで、近走の上昇と今回条件の方向が一致する。能力だけで抜けた馬がいないなら、今回はこの組み合わせを最も買いたい。

### 10R — Odori Koen Tokubetsu, 2-win Class, Dirt 1000m
◎ 10 パールフロント
Decision: TREND_ALIGNED

2勝クラスで直近2戦連続2着、Abilityもtypical52・latest53・peak57で今回上位。TrendとJRDB状態もSUPPORTIVEで、能力・近況・条件がほぼ同じ方向を向いている。懸念を探して別馬へ逃げるより、ここは素直に◎。

### 11R — Sapporo Kinen (G2), Turf 2000m
◎ 10 アドマイヤテラ
Decision: ABILITY_OVERRIDE

前走G1で3着、その前はG2を勝利しており、今回メンバーでは近走の格とAbilityが明確に上位。TrendはMIXEDだが、typical71・latest74・peak75という地力差を覆すほどの逆風とは判断しない。シェイクユアハートなど重賞実績馬も買えるが、「今回一番買いたい馬」という基準なら、まずこの地力を上に置く。

### 12R — Akan-ko Tokubetsu, 2-win Class, Turf 2600m
◎ 6 アスクデッドヒート
Decision: BALANCED_EVIDENCE

2勝クラスで2着を含め安定して戦っており、typical58は今回最上位。2600mのTrendにもプラス材料があり、RaceReviewでも同距離を含む上位クラスでの内容が確認できる。最新値49は懸念だが、一戦だけで地力評価を下げ切らず、クラス実績を優先して◎。

## Notes
- 5R 新馬は専用ロジック未整備のため暫定テスト。
- No result was consulted in making the above selections.
- ○/▲/△ are intentionally not selected.
