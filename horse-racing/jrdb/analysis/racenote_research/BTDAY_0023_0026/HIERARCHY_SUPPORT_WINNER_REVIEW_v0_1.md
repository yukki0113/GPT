# RaceNote Hierarchy研究 — △1 / △2 勝利30R Review v0.1

## Scope

BTDAY-0023〜0026 Discovery Set 144Rのうち、
`hierarchy_failure == true` かつ勝ち馬印が `△1 / △2` の30R。

△はcandidate setには入ったが、mainline上位にもsingle-shotにもならなかった馬。
結果だけで「本当は◎」としないため、Freeze時点のrace_model / mark_reason / RRDBへ戻って再評価した。

## Result

- REVERSAL_WARRANTED: **4/30**
- NARROW_GAP: **6/30**
- PRE_RACE_JUSTIFIED: **20/30**

※ annotationの内部値は他レビューとの整合上 `PROMOTION_WARRANTED` を使用。

## 30R review

| BTDAY | Race | winner mark | ◎ | winner | Assessment | 主因 |
|---|---|---|---|---|---|---|
| 0023 | 2026-05-03-新潟-1 | △1 | オートカリテ | オモイヲノセテ | PRE_RACE_JUSTIFIED | WEAK_SUPPORT_CASE |
| 0023 | 2026-05-03-新潟-2 | △1 | ビスケットアソート | エコロボルト | PROMOTION_WARRANTED | WIN_PATH_UNDERWEIGHT, SELF_MADE_PACE |
| 0023 | 2026-05-03-新潟-7 | △1 | ストレイトアスク | メランジェ | NARROW_GAP | WEAK_MAIN_EDGE, TRAINING_EDGE_SUPPORT |
| 0023 | 2026-05-03-東京-5 | △1 | オープンザパンドラ | オメガディコン | PROMOTION_WARRANTED | DIRECT_CONDITION_UNDERWEIGHT |
| 0023 | 2026-05-03-東京-6 | △2 | フルミネブル | リフレックス | PRE_RACE_JUSTIFIED | RECENT_FORM_EDGE |
| 0023 | 2026-05-03-東京-7 | △2 | マテンロウノカゼ | レッドベルダンス | PRE_RACE_JUSTIFIED | RECENT_FORM_EDGE |
| 0024 | 2026-02-01-京都-1 | △2 | ジーティービキニ | グラシアムヘール | PRE_RACE_JUSTIFIED | CONDITION_CHANGE_UNCERTAINTY |
| 0024 | 2026-02-01-京都-8 | △1 | ポンピエ | レイワサンサン | PRE_RACE_JUSTIFIED | DIRECT_CONDITION_EDGE_MAIN |
| 0024 | 2026-02-01-京都-9 | △2 | サンライズバレット | キングブルー | PRE_RACE_JUSTIFIED | DIRECT_CONDITION_EDGE_MAIN |
| 0024 | 2026-02-01-小倉-1 | △2 | ジョーカー | ラブインアクション | NARROW_GAP | DISTANCE_EXTENSION_UNCERTAINTY |
| 0024 | 2026-02-01-小倉-7 | △2 | タマモジャスミン | キャットテイル | PRE_RACE_JUSTIFIED | DIRECT_CONDITION_EDGE_MAIN |
| 0024 | 2026-02-01-小倉-9 | △1 | ドマーネ | ドーバーブライト | PROMOTION_WARRANTED | DIRECT_DISTANCE_UNDERWEIGHT, MODEL_CONTRADICTION |
| 0024 | 2026-02-01-小倉-11 | △2 | ハギノサステナブル | コトホドサヨウニ | PRE_RACE_JUSTIFIED | STRONG_MAIN_EVIDENCE |
| 0024 | 2026-02-01-東京-7 | △2 | ボウウィンドウ | ログラール | PRE_RACE_JUSTIFIED | DIRECT_CONDITION_EDGE_MAIN |
| 0024 | 2026-02-01-東京-8 | △1 | テーオーマルコーニ | ジーティーダーリン | PRE_RACE_JUSTIFIED | DIRECT_CONDITION_EDGE_MAIN |
| 0025 | 2026-02-15-京都-6 | △2 | ホワイトフレイムス | アヴィオン | PRE_RACE_JUSTIFIED | STRONG_MAIN_WIN_PATH |
| 0025 | 2026-02-15-京都-7 | △1 | ブリオメンテ | ロードヴォイジャー | PRE_RACE_JUSTIFIED | STRONG_MAIN_WIN_PATH |
| 0025 | 2026-02-15-京都-12 | △1 | ランウインディ | ルクスデイジー | NARROW_GAP | STABILITY_TIE |
| 0025 | 2026-02-15-小倉-1 | △1 | ロードアマルフィ | サムシングニュー | NARROW_GAP | TACTICAL_FIT_TIE |
| 0025 | 2026-02-15-小倉-5 | △1 | バンオンタイム | モウエエデショー | NARROW_GAP | HIDDEN_TIME_UNDERWEIGHT, SIGNAL_COMPETITION |
| 0025 | 2026-02-15-小倉-6 | △1 | ストレートブラック | ダノンジャイアン | PRE_RACE_JUSTIFIED | STRONG_MAIN_WIN_PATH |
| 0025 | 2026-02-15-小倉-9 | △1 | ウィルサヴァイブ | マトラコーニッシュ | PRE_RACE_JUSTIFIED | RECENT_FORM_EDGE |
| 0025 | 2026-02-15-小倉-10 | △2 | ハリウッドメモリー | メイショウセイロウ | PRE_RACE_JUSTIFIED | DIRECT_CONDITION_EDGE_MAIN |
| 0025 | 2026-02-15-東京-4 | △1 | ガンダ | ロンギングフォユー | PRE_RACE_JUSTIFIED | DIRECT_CONDITION_EDGE_MAIN |
| 0025 | 2026-02-15-東京-7 | △1 | マルセルテソーロ | ポッドベル | PRE_RACE_JUSTIFIED | STRONG_MAIN_SIGNAL |
| 0025 | 2026-02-15-東京-11 | △2 | ロブチェン | リアライズシリウス | PRE_RACE_JUSTIFIED | STRONG_MAIN_WIN_PATH |
| 0026 | 2026-01-24-京都-8 | △1 | ヴリトラハン | スペシャルナンバー | PRE_RACE_JUSTIFIED | RECENT_FORM_EDGE |
| 0026 | 2026-01-24-小倉-7 | △2 | ウインリュクス | スズカミエール | NARROW_GAP | TROUBLE_REBOUND, TRAINING_EDGE_SUPPORT |
| 0026 | 2026-01-24-小倉-11 | △1 | ココナッツブラウン | ジョスラン | PROMOTION_WARRANTED | DIRECT_CONDITION_UNDERWEIGHT, MODEL_CONTRADICTION |
| 0026 | 2026-01-24-小倉-12 | △1 | ホウオウバローロ | ラマンシュ | PRE_RACE_JUSTIFIED | DIRECT_CONDITION_EDGE_MAIN |

## Key finding 1 — △勝利の大半はcandidate-set success

30R中、事前材料から明確に主役昇格を支持するのは **4R**。

多くは:
- ◎に同条件実績がより強い
- ◎の勝ち切り像が具体的
- △は条件替わりや展開待ち
- △は「押さえる理由」はあるが主役にする理由ではない

という構造。

したがって△勝利を大量に学習してmarksを平坦化するのは逆効果。

## Key finding 2 — 修正候補は「直接条件」と「勝ち筋」

PROMOTION_WARRANTEDの中心:
- 0023 新潟2R: 両馬2着だが、△1は自分で逃げて耐えた。◎より勝ち筋が具体的。
- 0023 東京5R: 東京1800m戦で△1が同舞台実績、◎は2200mから短縮。
- 0024 小倉9R: 2600m戦で△1に直接2600m実績、◎は2200mから延長。
- 0026 小倉11R: 2000m戦で△1が前走2000m、◎は2200m。race_modelとも△1の方が整合。

○逆転研究と同じく、**race_modelが重視すると宣言した条件への直接性**が
最終Hierarchyで薄れるケースが繰り返されている。

## Key finding 3 — NARROW_GAPは印を入れ替えるより「差を作りすぎない」

NARROW_GAPは6R。
共通するのは:
- ◎と△の根拠がほぼ同型
- ◎側の優位が定性的
- △側に不利・調教上昇・hidden timeなど追加材料

この型は「△を◎へ昇格」ではなく、
mainline comparison内で不確実性を明示する方が自然。

## Combined Hierarchy conclusion

これまでの3群:

### ○ winner 23R
- REVERSAL_WARRANTED 7
- NARROW_GAP 4
- PRE_RACE_JUSTIFIED 12

### ▲ winner 11R
- PROMOTION_WARRANTED 1
- AMBIGUOUS_PROMOTION 1
- SINGLE_SHOT_SUCCESS_NO_PROMOTION 9

### △ winner 30R
- PROMOTION_WARRANTED 4
- NARROW_GAP 6
- PRE_RACE_JUSTIFIED 20

機械ラベル上のHierarchy failure 64Rを、
そのまま64件の「◎選択ミス」とみなすのは不適切。

現時点で明確なmainline序列修正候補は:
- ○群 7R
- ▲群 1R
- △群 4R
= **12R / 64R**

加えて境界的:
- ○群 4R
- ▲群 1R
- △群 6R
= **11R / 64R**

残る **41R / 64R** は、結果前の証拠では元のHierarchyが合理的、または▲の役割成功。

## Provisional pattern set

### P1 race_model consistency
race_modelで最重視した条件と◎○△の実際の証拠を最後に照合する。

### P2 direct-condition evidence
同コース・同距離・今回条件で既に示した能力を、
別条件の見栄えの良い着順より軽く扱っていないか。

### P3 runs-well vs can-win
2着・3着の安定を、勝ち切り・自力で動く・負荷下で耐える証拠より上に置いていないか。

### P4 ▲は別扱い
▲の勝利は原則single-shot success。
通常Hierarchyへ戻すのは、条件付き上振れではなくmainline級の直接勝ち切り証拠を既に持つ時だけ。

## Recommendation

Forecast v0.4.2の全面改修はまだ不要。

まずanalysis-sideで **Hierarchy consistency pass** を仮説化し、
未使用BTDAY Retest Setで、

- 事前にP1〜P3を検出できるか
- 12R型を拾いつつ41R型を壊さないか
- ◎勝率/単勝ROIだけでなく○・▲との馬券構造が改善するか

を確認してからForecast本体への採用を判断する。

## Next

Hierarchy研究は一旦完了。
次は **Coverage研究** に進む。
