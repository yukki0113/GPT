# RaceNote Hierarchy研究 — ◎ vs ○ 逆転23R Review v0.1

## Scope

BTDAY-0023〜0026 Discovery Set 144Rのうち、
`hierarchy_failure == true` かつ勝ち馬印が `○` の23Rを対象にした。

正本:
- `research_population.jsonl`
- 各BTDAYの Freeze Forecast `day_merge/forecast_*_all.json`

結果は対象レースの抽出にのみ使用し、序列修正の可否は Freeze 時点の
`race_model / mainline_cases / mark_reason / rrdb_evidence` に戻って判定した。

## Assessment contract

- **REVERSAL_WARRANTED**: 結果を知らなくても、Freeze時点の材料だけで○を◎より上へ置く再現可能な根拠がある。
- **NARROW_GAP**: ○を上へ置く決定打まではないが、◎と○の差を小さく扱うべき材料がある。
- **PRE_RACE_JUSTIFIED**: ○が勝った事実だけでは修正しない。Freeze時点では◎優先が合理的。

## Result

- REVERSAL_WARRANTED: **7/23**
- NARROW_GAP: **4/23**
- PRE_RACE_JUSTIFIED: **12/23**

つまり○逆転23Rのうち、現時点で「Hierarchyの再現可能な誤差」と見なせるのは7R。
残り16Rを結果論で◎失敗として学習させない。

## 23R review

| BTDAY | Race | ◎ | ○(winner) | Assessment | 主因 |
|---|---|---|---|---|---|
| 0023 | 2026-05-03-京都-9 | サンライズバレット | レヴァンテシチー | REVERSAL_WARRANTED | VISIBLE_FINISH_OVERWEIGHT, HIDDEN_LOAD_UNDERWEIGHT |
| 0023 | 2026-05-03-京都-11 | アドマイヤテラ | クロワデュノール | PRE_RACE_JUSTIFIED | DISTANCE_UNCERTAINTY |
| 0023 | 2026-05-03-新潟-12 | フルドド | タケルハーロック | PRE_RACE_JUSTIFIED | RECENT_FORM_EDGE |
| 0023 | 2026-05-03-東京-2 | ライカ | レピュニット | PRE_RACE_JUSTIFIED | SURFACE_CHANGE_UNCERTAINTY |
| 0023 | 2026-05-03-東京-12 | ルーフオブヘヴン | エイプリルインパリ | PRE_RACE_JUSTIFIED | RECENT_FORM_EDGE |
| 0024 | 2026-02-01-京都-3 | パラダイスフェイス | アスクチャンスマン | REVERSAL_WARRANTED | DIRECT_CONDITION_UNDERWEIGHT, MODEL_CONTRADICTION |
| 0024 | 2026-02-01-東京-5 | サトノフレイ | アスクイキゴミ | PRE_RACE_JUSTIFIED | NEWCOMER_UNCERTAINTY |
| 0025 | 2026-02-15-京都-2 | ヨウリンケイジュ | ハノハノ | NARROW_GAP | NEWCOMER_UNCERTAINTY, WIN_PATH_UNDEREXPRESSED |
| 0025 | 2026-02-15-京都-5 | ダーリンダーリン | ピカキウイ | NARROW_GAP | TACTICAL_FIT_UNDERWEIGHT |
| 0025 | 2026-02-15-小倉-4 | カイコウ | アルカンサス | PRE_RACE_JUSTIFIED | SPECIALTY_RACE_UNCERTAINTY |
| 0025 | 2026-02-15-小倉-12 | ウィズマスタング | マーウォルス | PRE_RACE_JUSTIFIED | DIRECT_CONDITION_EDGE_MAIN |
| 0025 | 2026-02-15-東京-3 | プレースメント | タイセイジェイド | PRE_RACE_JUSTIFIED | NEWCOMER_UNCERTAINTY |
| 0025 | 2026-02-15-東京-5 | サムシングスイート | ナックホワイト | PRE_RACE_JUSTIFIED | EVIDENCE_TIE |
| 0025 | 2026-02-15-東京-6 | ノラリクラリ | ティムール | NARROW_GAP | DIRECT_DISTANCE_ABILITY_UNDERWEIGHT |
| 0025 | 2026-02-15-東京-9 | アンパドゥ | ダノンセンチュリー | PRE_RACE_JUSTIFIED | RECENT_WIN_CEILING_MAIN |
| 0025 | 2026-02-15-東京-12 | モーニングマジック | クインズデネブ | REVERSAL_WARRANTED | MODEL_CONTRADICTION, PACE_SCENARIO_UNDERWEIGHT |
| 0026 | 2026-01-24-中山-2 | アイデアユー | スノースコール | PRE_RACE_JUSTIFIED | STRONG_MAIN_EVIDENCE |
| 0026 | 2026-01-24-中山-11 | ショウナンラピダス | エセルフリーダ | REVERSAL_WARRANTED | FAVORABLE_TRIP_OVERWEIGHT, DIRECT_CONDITION_UNDERWEIGHT |
| 0026 | 2026-01-24-京都-1 | タガノシルフィー | シャフメラン | REVERSAL_WARRANTED | VISIBLE_FINISH_OVERWEIGHT, HIDDEN_LOAD_UNDERWEIGHT |
| 0026 | 2026-01-24-京都-5 | マテンロウオリジン | ブラックオリンピア | REVERSAL_WARRANTED | MODEL_CONTRADICTION, NEGATIVE_MAIN_FACTOR_UNDERWEIGHT, HIDDEN_LOAD_UNDERWEIGHT |
| 0026 | 2026-01-24-京都-12 | メイショウカイト | エイムフォーエース | PRE_RACE_JUSTIFIED | STRONG_MAIN_EVIDENCE |
| 0026 | 2026-01-24-小倉-6 | ウォータールスール | ボンドマティーニ | REVERSAL_WARRANTED | MODEL_CONTRADICTION, TRAINING_HIERARCHY_INCONSISTENCY |
| 0026 | 2026-01-24-小倉-10 | サラトガチップス | キングスコール | NARROW_GAP | ADVERSITY_UNDERWEIGHT, TRAINING_EDGE_SECOND |

## Reproducible error patterns

### H1. race_model と最終Hierarchyの不整合

最も強い修正候補。

該当の中心:
- 0024 京都3R: 「1900m実績を重視」なのに、同条件3着の○より1800mから延長の◎を上位。
- 0025 東京12R: 「前半が流れやすい」想定なのに、「前が競れば主役まで届く」○を対抗止まり。
- 0026 京都5R: 「折り合って長く脚」を重視する2200mで、明示的に「折り合い×」の◎を最上位。
- 0026 小倉6R: 新馬で調教中心のrace_modelなのに、記録された調教評価は○の方が上。

**示唆:** marks決定後に、`race_model -> ◎○の序列` が論理的に一致しているかを再確認する
Hierarchy consistency pass が有効そう。ただし点数化や固定ルール化はしない。

### H2. 表面着順 / 安定感を、負荷下の勝ち切り・耐性より上に置く

該当の中心:
- 0023 京都9R
- 0026 京都1R
- 0026 中山11R

共通構造:
- ◎側: 2着など見栄えの良い直近結果、安定感
- ○側: 前傾耐性、仕掛け遅れ、同条件、勝ち切りなど「今日勝つ」に接続しやすい材料
- Readerは○の材料を認識しているが、最終比較で◎の見栄えを優先

これはv0.4.2の目的である
「runs well」と「can win」の区別が、まだHierarchy決定で完全には効いていない可能性がある。

### H3. 条件直接性を、一般的な好走再現性より軽く扱う

該当:
- 0024 京都3R
- 0026 中山11R
- 一部NARROW_GAP: 0025 東京6R

距離・コース・今回条件への**直接的な証拠**が○側にあるのに、
◎側の近走安定・一般的な持続力を上に置くケース。

### H4. 新馬は別問題

新馬の○逆転:
- 0024 東京5R
- 0025 京都2R
- 0025 東京3R
- 0026 小倉6R

4R中、明確な修正候補は0026小倉6Rのみ。
他は事前情報が薄く、勝者を見てから序列を説明し直す危険が高い。

新馬については通常Hierarchyと同じ精度の原因分類を期待しない方がよい。

## What should NOT be learned

以下は「○が勝った」だけでは修正対象にしない。

- ◎に同距離/同コースの明確な好走実績がある
- ◎にRRDBの強い事前再評価材料があり、○には対抗する材料がない
- 新馬で事前能力差を覆す情報が記録上ない
- ○の勝ち筋が結果後にしか明確にならない

特に:
- 0023 東京2R
- 0026 中山2R
- 0026 京都12R

は、結果を知らずに再比較しても◎を維持するのが自然。

## Provisional Hierarchy hypothesis v0.1

Forecast本体を直ちに変更するのではなく、次の研究仮説として保持する。

> ◎○を決めた後、race_modelと両者のcase_forをもう一度並べ、
> 「race_modelが最重視すると宣言した条件を、実際により強く満たすのはどちらか」
> 「◎の根拠は好走・安定を示すだけで、○側により直接的な勝ち切り材料がないか」
> を意味ベースで再確認する。

これはscore/weightではなく、既存Human-Context Readerの比較工程を
もう一度明示的に閉じるための consistency check 仮説。

## Next

次は **▲逆転11R** を同じ方法でレビューする。

見るポイント:
1. single-shot case が勝利まで届く強さを事前に持っていたか
2. ▲をmainlineと直接比較しない設計が妥当だったか
3. ▲定義は維持したまま、主役候補への昇格を検討すべき型があるか
