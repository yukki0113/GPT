# RaceNote v0.5.6 — W/R/U/D 勝ち切る比較優位 Shadow Freeze 運用仕様

更新日: 2026-11-11 / Status: RESEARCH-ONLY / PROTOCOL & TOOLING

## 目的と不変条件
- 正式なA/B/C/Zは勝ち馬としての◎の優位への確信度。W/R/U/Dは**既存の正式Confidenceを変更しない研究用Shadow**。
- Prediction Freeze → Confidence Freeze → 独立W/R/U/Dレビュー → Shadow Freeze → 結果照会、の順。旧Prediction、印、正式Confidence、既存二段階Freezeは不変。
- 0183〜0185は今回既に通常ConfidenceがFreezeされているが、当時W/R/U/Dの独立Freezeがなかった。**この3回を後付けで前方Shadow実験に認定してはならない。**
- 0175と0183は同日2025-03-29、0169と0184は同日2025-11-08のリプレイ。独立開催日を二重計数しない。

## 新規BTDAYの操作手順

1. 新しい、まだ結果未照会のBTDAYで、通常のPredictionとConfidenceのFreezeを完了し、GitHub mainへのSHA記録・読み戻しまで実施する。
2. 同日結果・払い戻し・対象日市場を**まだ参照していない担当者**が、以下のテンプレートを作る（パス中のXXXXとYYYYMMDDを置換）。

~~~bash
ROOT=horse-racing/jrdb/backtests/BTDAY-XXXX/YYYYMMDD/v056
python horse-racing/jrdb/src/racenote_v056_wrud_shadow.py \
  --mode template --root "$ROOT" \
  --output "$ROOT/research/wrud/incoming/review.json"
~~~

3. 各標準平地レースにつき正式◎と自信度を固定したまま、次の5つを独立著述する。自動判定は禁止。
   - W / winning_route: 今回条件で◎が1着になる具体的な勝ち筋。連対反復は補助証拠であって勝利の保証ではない。
   - R / rival_relative_advantage: ○・▲などが勝ち得る経路を比較しても◎を上位とできる根拠。
   - U / uncertainty_defeat_test: 本命が負ける重要経路、それを覆す事前根拠、解消できない不確実性。
   - D / distinctive_evidence: そのレース固有の事前材料（同文の使い回しは禁止）。
   - shadow_reason: 4観点を総合し、研究用Shadow A/B/Cとした理由。Rと同一文のコピペは禁止。
4. 各レースのshadow_confidenceを人間／LLMがA/B/Cで判断する。ZはZを保持し、5つの説明フィールドはnullのままとする。Aを増減するための固定閾値や件数ノルマは禁止。
5. evidence_attestation内の3つの項目(result_not_accessed_by_reviewer, target_market_not_accessed_by_reviewer, review_authored_before_result_query)は、真実として宣誓できる場合のみtrueにし、attested_byに担当者を記す。GitHub Actionsは宣誓の真正性を独立に確認できない。
6. 手元でvalidationを実行。

~~~bash
python horse-racing/jrdb/src/racenote_v056_wrud_shadow.py \
  --mode validate --root "$ROOT" \
  --draft "$ROOT/research/wrud/incoming/review.json"
~~~

7. VALID後にincoming/review.jsonをGitHub mainへコミット。専用Workflow racenote_v056_wrud_shadow_freeze.ymlが公式Freeze正本SHA、全レース、正式印・Confidence不変、証拠説明、宣誓を検査し、research/wrud/frozen/records.jsonとseal.jsonを**別領域に追加コミット**。
8. Workflow終了、GitHub mainでseal.jsonを読み戻し、status=WRUD_SHADOW_FROZENとSHAを確認**してから**対象日の結果照会を実行。失敗時は結果を開かずに修正。Shadow Frozenが既に存在したら上書き拒否。

## 既存記録で再現性を調べた結果
- 0175→0183: Confidence変更18/36、旧B→A 8、C→A 1、旧C→B 8、B→C 1。新A9Rすべて◎不変。理由は同条件2着・3着の実績を勝利の決定的比較優位として採用する方向に変化。
- 0169→0184: Confidence変更11/36、旧B→A 3、A→B 4、B→C 4。逆に○の同条件勝利実績や相手の直接適性を重く見てAを控える場面もある。
- 0183〜0185のA26件は、すべてfinal_grade_reasonとrelative_advantageの文字列が同一で、最終判断と相対証拠の役割の違いが表面化していなかった。ただし勝敗は未照会、判定が誤っていたとの断定はしない。
- 当日既知の結果を使って研究用Shadowを作っても、レトロスペクティブ診断であって前方Shadowではない。

## プログラムが保証するもの／しないもの
保証する: 正式Frozen recordsのSHAとhandoffの一致、レースキーと◎と正式Confidenceの同一性、全レースの収録、Zの隔離、空欄と説明文コピペの形式検査、Shadow不変SHAシール、同じShadowの上書き拒否。

保証しない: 人間が結果を知っていなかったことの独立証明、記述が実質的に勝利優位を説明できていること、Shadowグレードの統計的妥当性、購入時オッズや利益。GitHub上のコミット時刻と人間の宣誓は監査材料であり、それだけで完全なBlindは証明しない。

## 初回検証と指標
新規の重複しないBTDAY 5回でフォーム、説明分離、SHA、意図しない結果混入を監査。問題なければ20独立BTDAY程度まで進める。主指標は公式A/B/Cと研究用Shadowの遷移、Shadow Aの件数・◎勝率・誤差範囲・開催日別安定性。単勝ROIは別の副次指標。B/Cの定義を「3着内軸」に戻さない。市場オッズでConfidenceを決めない。

初期段階では自動評価・自動公開・自動馬券購入は行わない。
