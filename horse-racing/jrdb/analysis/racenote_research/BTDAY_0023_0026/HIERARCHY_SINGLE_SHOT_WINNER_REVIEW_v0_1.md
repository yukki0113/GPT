# RaceNote Hierarchy研究 — ▲勝利11R Review v0.1

## Scope

BTDAY-0023〜0026 Discovery Set 144Rのうち、
`hierarchy_failure == true` かつ勝ち馬印が `▲` の11R。

ただし▲は現行定義上、◎○を負かしてよい。
そのため「▲が勝った = Hierarchy failure」という機械ラベルを、そのままロジック失敗とは扱わない。

## Assessment contract

- **SINGLE_SHOT_SUCCESS_NO_PROMOTION**: ▲の勝利は事前single-shot caseの成功。◎へ昇格させる必然性はない。
- **PROMOTION_WARRANTED**: Freeze時点でも▲をmainlineへ戻して◎候補として比較する根拠が強かった。
- **AMBIGUOUS_PROMOTION**: mainline再比較の余地はあるが、昇格必須までは言えない。

## Result

- SINGLE_SHOT_SUCCESS_NO_PROMOTION: **9/11**
- PROMOTION_WARRANTED: **1/11**
- AMBIGUOUS_PROMOTION: **1/11**

▲勝利11Rの大半は、Hierarchy誤差ではなくsingle-shot設計の成功と解釈する。

## 11R review

| BTDAY | Race | ◎ | ▲ winner | Assessment | 主因 |
|---|---|---|---|---|---|
| 0023 | 2026-05-03-京都-1 | スマッシング | ピカラ | SINGLE_SHOT_SUCCESS_NO_PROMOTION | HIDDEN_ABILITY_SIGNAL, MAIN_DIRECT_FORM_STRONG |
| 0023 | 2026-05-03-新潟-5 | レインボーステート | ワールドブレイヴ | SINGLE_SHOT_SUCCESS_NO_PROMOTION | REAR_LATE_SIGNAL, DISTANCE_CHANGE_UNCERTAINTY |
| 0023 | 2026-05-03-新潟-11 | ポールセン | ブレーザー | AMBIGUOUS_PROMOTION | TROUBLE_REBOUND, WEAK_MAIN_EDGE |
| 0023 | 2026-05-03-東京-10 | クールミラボー | タイトニット | SINGLE_SHOT_SUCCESS_NO_PROMOTION | LATE_UPSIDE, STRONG_MAIN_EVIDENCE |
| 0024 | 2026-02-01-小倉-12 | ジェニファー | セイウンデセオ | SINGLE_SHOT_SUCCESS_NO_PROMOTION | PACE_COLLAPSE_CASE, REAR_LATE_SIGNAL |
| 0024 | 2026-02-01-東京-2 | ホウオウファミリー | オルブライト | SINGLE_SHOT_SUCCESS_NO_PROMOTION | DISTANCE_EXTENSION_UPSIDE, STRONG_MAIN_EVIDENCE |
| 0024 | 2026-02-01-東京-4 | マックスキュー | ベラジオワールド | SINGLE_SHOT_SUCCESS_NO_PROMOTION | CONDITION_CHANGE_UPSIDE, TRAINING_SPIKE |
| 0024 | 2026-02-01-東京-10 | ユハンヌス | ウイントワイライト | PROMOTION_WARRANTED | DIRECT_COURSE_WIN_UNDERWEIGHT, HIDDEN_LOAD_UNDERWEIGHT |
| 0025 | 2026-02-15-東京-8 | ジャサルディア | エフォートレス | SINGLE_SHOT_SUCCESS_NO_PROMOTION | PACE_DEPENDENT_UPSIDE, REAR_LATE_SIGNAL |
| 0026 | 2026-01-24-中山-5 | ウィロークリーク | ミッキーファルコン | SINGLE_SHOT_SUCCESS_NO_PROMOTION | SUPPORTING_STAMINA_CASE, STRONG_MAIN_EVIDENCE |
| 0026 | 2026-01-24-京都-2 | ラヴネヴァーダイズ | リアルアルバ | SINGLE_SHOT_SUCCESS_NO_PROMOTION | ADVERSITY_REBOUND, STRONG_MAIN_EVIDENCE |

## Key finding 1 — ▲をmainlineへ常時比較し直さない

以下のような▲は、勝っても役割成功であり、◎昇格漏れではない。

- 前崩れ時だけ浮上する差し
- 条件替わりで大きく上振れる馬
- 前走不利を解消した時だけ反転する馬
- 距離延長で追走が楽になる馬
- RRDBが示す隠れた末脚・能力を持つが通常信頼度は低い馬

これらを結果後に◎候補へ昇格させると、single-shotの非対称性を失う。

## Key finding 2 — 昇格候補は「条件付き魅力」ではなく「本線の勝ち切り根拠」を既に持つ場合

明確なPROMOTION_WARRANTEDは **0024東京10R ウイントワイライト**。

Freeze時点で:
- 東京1400mの差し切り勝ち実績
- 条件戻り
- REAR_HIGH_LAST3F90
- ◎ユハンヌスは1400m連続3着の安定型

という構造。

これは▲の単なる上振れではなく、
「◎ = runs well」「▲ = same-condition win ceiling」
になっており、v0.4.2が避けたいHierarchy逆転パターンに近い。

## Key finding 3 — single-shot promotion gate の仮説

▲を◎○へ常時比較するのではなく、以下を満たす時だけmainlineへ戻す方がよい。

1. ▲のcase_forが「もし展開が噛み合えば」だけではなく、今回条件そのものへの直接的な勝ち切り証拠を含む
2. 同コース・同距離勝ち、強い負荷下の勝利、明確なクラス能力など通常mainlineでも通用する証拠がある
3. ◎側が「安定して2/3着」の根拠に寄っている
4. ▲をmainlineへ戻しても、単に未知条件の上振れを過大評価することにならない

このgateはscore化せず、意味ベースの再比較として研究する。

## Implication for mechanical labels

今後のHierarchy研究では
`hierarchy_failure = winner_in_five && !main_won`
をそのまま「予想ロジックの失敗数」と呼ばない。

少なくとも:
- winner_mark = ○ / △ → hierarchy ordering error候補
- winner_mark = ▲ → single-shot success と promotion miss を分離

する必要がある。

## Next

次は **△1 / △2 逆転30R**。
候補集合には入っていたがmainlineにもsingle-shotにも上がらなかったケースなので、

- 地味な条件一致の過小評価
- 安定性の過小評価
- 未知要素の嫌いすぎ
- mainline候補4頭内の順位圧縮

を中心に見る。
