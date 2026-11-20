# BRDB 道悪注目観測 選別 v0.5 candidate — 2026-11-20

**RESEARCH ONLY / NOT AN APTITUDE MODEL / NO RACENOTE OR PWA AUTHORISATION**

## 目的

v0.4 の「良 vs 道悪（稍重・重・不良）」父産駒観測から、レビュー候補として再確認する価値がある差だけを機械的に抽出する。抽出結果は「道悪適性」「好材料」「買い材料」ではなく、あくまで **注目観測**。RaceNote、PWA、血統DBレビュー本文にはまだ接続しない。

## 選別ルール

全ルールは同一scope内の良/道悪比較に対して適用する。

- `STRONG_DESCRIPTIVE`: 良・道悪の小さい方の母数 >= 30、複勝率差の絶対値 >= 8.0pt、かつ両群の95% Wilson区間が非重複。
- `NOTABLE_DESCRIPTIVE`: 小さい方の母数 >= 20、複勝率差の絶対値 >= 5.0pt。
- `LOW_SAMPLE_SIGNAL`: 小さい方の母数 >= 5、複勝率差の絶対値 >= 10.0pt。小標本なので強い結論へ昇格させない。
- それ以外は `ROUTINE_OBSERVATION` とし、選別対象外。

この閾値は「科学的に最適化済みの予測閾値」ではなく、研究レビュー量を制御するための **v0.5候補のトリアージ規約**。M6-P等の予測有効性検証とは別物。

## scope重複の扱い

5 scope は包含関係があり独立標本ではない。複数scopeが同方向でも「独立した裏付けが複数ある」とは数えない。

馬ごとのprimaryは、差の大きさで選ばず、選別対象になった中で今回条件に最も近いscopeを優先する。

1. VENUE_COURSE_DISTANCE
2. VENUE_DISTANCE
3. ALL_VENUES_DISTANCE
4. VENUE_BAND
5. ALL_VENUES_BAND

scope間の符号が同じなら `CONSISTENT`、正負が混在するなら `MIXED`。これは記述上の整合性で、統計的独立性や因果的な再現性を意味しない。

## 実データ再演の受入方針

2026-11-15 東京12Rの18頭について、公開DriveのSHA固定済みAnalysis v1.4（2016–2026）とPACIをBRDB研究Actionsで再演する。v0.4をメモリ内で生成後、このv0.5選別を実行する。

公開Actions artifactには馬名、馬ID、父名、個別成績を残さず、以下の集計だけを監査出力する。

- 候補が1件以上ある馬数
- tier別候補数
- NON_GOOD_HIGHER / GOOD_HIGHER の件数
- primary scope分布
- scope方向がCONSISTENT / MIXEDの馬数

## 保留事項

- 分母は引き続き `NORMAL_FINISHERS_ONLY` で、正式な出走数定義ではない。
- historical pedigree profileは `AS_OF_UNVERIFIED`。
- 道悪3状態（稍重・重・不良）を統合している。4状態個別比較は未実装。
- 多重比較補正、階層モデル、ベイズ縮約、ROI、予測妥当性は未実装。
- `display_eligible=false`, `prediction_eligible=false`, `production_authorized=false` を維持する。
