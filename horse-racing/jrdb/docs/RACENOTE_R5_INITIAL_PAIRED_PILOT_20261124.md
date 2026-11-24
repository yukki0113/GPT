# R5 初回A/B研究検証 — 2026-11-24

判定: **PASS_INITIAL_HISTORICAL_PAIRED_PILOT_ONLY / R5全体PARTIAL / R6未承認**。予想精度改善の認定なし。既存v0.5.6本番、Reader/KYI allowlist、Confidence定義、凍結成果物、CURRENT、PWAは変更しない。

## 1. 事前固定と実行境界

[事前固定protocol](RACENOTE_R5_PAIRED_RESEARCH_PROTOCOL_20261124.md) を commit `9968b6723facbb790212e0b7f555493afd1b7218` で保存・読み戻し後にB著述。R4の同一Reader・両DB取得済み全3R（2026-11-15東京4・5・12R、A1 2R22頭/OTHER 1R18頭）を使用。6月3Rは同版封印Reader未取得、通常1RはBRDB未取得。結果選別なし。Aは当時のPrediction/Confidence Freeze、Bは同じv056 Reader + R3研究用観測。R4 B5・制限参照は数値利用せず。Bは別研究形式（正式v056 Decision Core/本番Freezeへの投入ではない）。LLM手著述、固定加点・自動印なし。B予想をLibraryに保存・読み戻し確認後、B Confidenceを別途著述・保存・読み戻し確認。両者のSHA一致後A記録を取得し、元handoff SHAと一致。対象結果はその後に正本JRDB Result Query runnerでSED/HJCを取得・照合、3R40頭異常なし・全top3およびSED/HJCクロス検証PASS。Web不使用。

B Prediction SHA `ba44c7bedec39eaae18c263fb0c760d953c5638eaaa73ab8b2102cc7dce8c810`、B Confidence SHA `394ce65f3499929dc83246a36e7e27992e0c9932f0c32338c2ad9c27d623e4ae`。Aの既存SHA、原sourceおよび結果SHAは集計receipt。過去日であり、記憶・事前知識の排除を証明できず、Aの当時のauthor/model差も交絡する。TRUE_FORWARD/厳密as-of/controlled causal effectではない。

## 2. 事前固定指標

| 指標 | A1 A | A1 B | OTHER A | OTHER B |
|---|---:|---:|---:|---:|
| ◎1着 | 1/2 | 0/2 | 0/1 | 0/1 |
| ◎3着内 | 1/2 | 1/2 | 0/1 | 0/1 |
| 印5頭内に勝ち馬 | 2/2 | 2/2 | 1/1 | 1/1 |
| 印5頭内の3着内馬 | 4/6 | 5/6 | 1/3 | 1/3 |
| 印5頭で全3着内馬を包含 | 1/2 | 1/2 | 0/1 | 0/1 |

A1の◎変更2R、印5頭変更2R（昇格2・脱落2）、OTHERは◎/集合不変・▲変更。A1の勝ち切り1R悪化・1R同等、印5頭内top3数1R改善・1R同等。OTHERは全指標同等。A1 Z→Z、OTHER B→C（勝ち切り序列の不確実性増加、着内軸定義への変更なし）。ROI・確率・因果的な寄与は測定しない。

## 3. 読解監査（著者自己レビュー、独立評価未実施）

B全40頭を個別著述、106根拠参照が同一馬のR3詳細に実在。A1 22/22頭・OTHER 18/18頭。新しい根拠による再検討ラベル14頭（A1 6、OTHER 8）、SUPPORT 10、CONCERN 14、UNCERTAIN 2。参照馬数JPDB 32/40・BRDB 39/40、非参照は欠損の意味ではない。新馬戦の候補選別改善は4Rの1頭の拾い直しによる。5Rでは強い既存材料に加え騎手の新馬芝実績等から本命を変更したが、勝ち切り判断は悪化。同距離の相対低下も併記していたため、広い条件の観測が勝ち切り判定を支配しすぎないか検討が必要。通常戦では血統・騎手から条件適性の再検討対象を発見したが、実走材料との比較で5頭への昇格を見送った。結果的に上位の伏兵を拾えなかった。結果から事後的に印や根拠・閾値を変更しない。相対差・絶対率、父母父の重複、少数個体、交絡、矛盾、B5履歴gapを区別したが、構造検査は数値・文章の意味論を完全認証しない。個別再検討の適否・独立再読は次期課題。

## 4. 再現と保存

`src/racenote_r5_paired_audit.py` は固定pilotのA/Bハッシュ・B Library読み戻し・R4 manifest・全馬・参照・Confidence・結果照合・集計のみ。予想生成なし。`tests/test_racenote_r5_paired_audit.py` 8/8 PASS、集計receipt二回byte一致。異常着順/取消等は当pilotでは0、再演に異常があればfail closedして手動監査する（未来の汎用評価を実装したとの主張ではない）。個体別判断、A原記録、結果、再演元SHA、著述・閲覧補助コードは非公開Library `/JPDB/R5/JPDB_R5_20261124_private_pilot.zip` に保存、読み戻し一致。Gitは集計・コード・文書のみ。[集計証跡](evidence/racenote_r5_initial_pilot_20261124.json)。

実行: `python src/racenote_r5_paired_audit.py --manifest <R4固定private_manifest> --a-pred <A records> --a-conf <A confidence records> --b-pred <B prediction> --b-conf <B confidence> --b-pred-readback <B prediction Library readback> --b-conf-readback <B confidence Library readback> --result-dir <canonical query result_N_all.json> --output <new aggregate receipt>`。R4 manifestの参照先は元の固定パス/原本SHAに復元して使用する。`PYTHONPATH=horse-racing/jrdb/src python -m unittest discover -s horse-racing/jrdb/tests -p test_racenote_r5_paired_audit.py -v`。

## 5. 残工程

R5初回研究実測完了、R5全体未完。事前固定protocolの50R読解監査（A1/OTHER各25Rを目標、対象前に実レース一覧・入力SHA・モデル/論理版・独立著述条件を固定）、TRUE_FORWARD両系統予想/Confidence Freeze、独立意味論監査を次に行う。50Rは性能認証の十分数ではない。B5数値を使う場合は別の明示的研究契約と独立比較、JPDB/BRDB単独寄与のablationは別計画。R6昇格を保留。
