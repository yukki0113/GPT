# BRDB ④ 兄姉・母方近親の類似条件実績 — 研究用 v0.1

- 検証日: 2026-11-05
- Status: **RESEARCH ENGINE IMPLEMENTED / LOCAL REAL-RACE PROBE PASS / SYNTHETIC TESTS 5/5 PASS / NOT PREDICTION-SAFE**
- 実装: `../src/run_brdb_relatives_evidence.py`
- 回帰: `../tests/test_brdb_relatives_evidence.py`
- 対象: 2026-11-01 東京5R・芝2000m（PACI261101.zip、race_key `05264b05`、8頭）
- 血統研究用世代: `5279af0bd8226cde`、血統fact `pedigree_fact.parquet` と関係 `parent_relation.parquet` をmanifest SHA検証して利用。**現行BRDB CURRENTへの変更なし。**
- 結果: JRDB Analysis v1.4 CURRENT。出走結果は `2016-11-01 <= race_date < 2026-11-01` の10年間。
- **本書は予想ではない。RaceNote本番への採用や⑤の血統好材料判定は未実施。**

## 1. 身元同定・血縁区分

対象出走馬はPACI KYI血統登録番号で識別し、父母の正式データは同日UKCを共通JRDB Readerで取得。馬名のみでの身元結合は禁止。

- **母馬の同定:** 研究用血統factで `母名+母生年+性別(牝)+母父名+母父の公式父系コード` が完全一致し、かつ候補が一意・profile_data_date<=対象日となる母のcanonical `horse_id`のみ採用。候補ゼロ/複数/矛盾はSOURCE_UNAVAILABLE。
- **母を共有する兄姉:** 研究用 `parent_relation.role=dam` が `RESOLVED_EXACT` または `RESOLVED_ALIAS` で同じ `resolved_parent_horse_id` を指す馬のみ。対象馬より**生年月日が早い**馬に限定する。
- **全兄姉:** 上記に加え、対象馬の父canonical IDも独立に一意・整合確認でき、兄姉の `parent_relation.role=sire` 解決先IDと一致した場合のみ `FULL_SIBLING`。父名だけ一致した場合は `SAME_DAM_SAME_SIRE_NAME_UNVERIFIED` で保留。
- **母方のおじ・おば:** 対象馬の母 `role=dam` から母方祖母canonical IDが確認でき、その祖母を母に持つ別の子をcanonical relationで解決した場合のみ `MATERNAL_AUNT_UNCLE`。甥姪・いとこ・父方おじおば・3〜5代の遠縁を包括的に検索した実装ではない。
- 近親のプロフィール日付も `<=target_date` を要求。未解決の母/祖母から見つからないことは**血縁関係が存在しない証明にはならない**。
- 実行時には血縁候補の登録年度・出生順を保存する。母が同定できたか否かと出走実績の有無は別の状態で返す。

## 2. 類似条件での近親実績

①で確定した「芝ダを混ぜない5階層」を④でも使う。

1. `VENUE_COURSE_EXACT`: 同場・同芝ダ・同コースコード・同距離
2. `VENUE_DISTANCE`: 同場・同芝ダ・同距離
3. `VENUE_BAND`: 同場・同芝ダ・同距離帯
4. `ALL_VENUES_DISTANCE`: 全場・同芝ダ・同距離
5. `ALL_VENUES_BAND`: 全場・同芝ダ・同距離帯

各近親について `horse_id`, `horse_name`, `relationship`, `birth_date`, `profile_data_date`, `scope_stats`（出走・勝ち・3着内数・複勝率）を返す。取消/除外は出走数に含まず、競走中止/失格/降着/再騎乗は実出走数に含む。勝利/3着内は通常/降着の記録を使う。0走は `top3_rate=null` であって0%ではない。

系統レベルの代替や親族の3着内を対象馬の複勝率へ代入する処理はない。近親ごとの観測は、能力・父の違い・同一馬の反復出走・出走条件選択を考慮した予測値ではない。

## 3. 東京5R・8頭の照合結果

| 馬番 | 対象馬 | 同一母の兄姉 | 母方のおじ・おば | 近親のうち全場・芝中距離（1800〜2399m）に1走以上 |
|---:|---|---:|---:|---:|
| 1 | ショウナンサザン | 2 | 9 | 7 |
| 2 | オルトゥス | 2 | 2 | 1 |
| 3 | ロイヤルヴェイズ | 3 | 6 | 6 |
| 4 | ベルウッドイタル | 5 | 0確認 | 4 |
| 5 | アドマイヤミラ | 0確認 | 4 | 2 |
| 6 | パルパデオ | 未確認 | 未確認 | 未確認 |
| 7 | キャナルタウン | 2 | 0確認 | 2 |
| 8 | アイアムスグレモノ | 未確認 | 未確認 | 未確認 |

- **母馬のcanonical ID同定 6/8頭**。残り2頭は後年名の推測では埋めず `SOURCE_UNAVAILABLE`。
- 母を共有する兄姉14頭（全兄姉1頭、母方半兄姉13頭）、母方のおじ・おば21頭で、**計35頭の異なる近親**。
- うち21頭が全場・芝中距離に1回以上の過去出走記録を持つ。出走歴ゼロの馬も「適性が低い」ではなく証拠不足。
- 例: ロイヤルヴェイズの母方半兄姉「エデルクローネ」は、全場・芝1800〜2399mで7走・3着内6回（対象馬本人の適性を保証せず、小母数）。
- 例: キャナルタウンの母方半兄姉「アクアヴァーナル」は、同距離帯で9走・3着内4回（同上）。
- 例: オルトゥスの全兄姉認定は、母のcanonical IDと父のcanonical IDの**双方一致**に基づく。
- 0件と表記した箇所は「この採用条件・研究コホートで確認0」の意味で、実在する近親がゼロとの断定ではない。

## 4. 性能・検証範囲

- ローカル CPython3.13 + DuckDB1.1.3。
- 8頭をPACIから抽出し、研究用血統2ファイルのSHA検証・canonical血縁探索・Analysis11年別ParquetのSHA検証・過去実績集計まで**約0.65〜0.75秒**（Drive転送時間を除く）。
- 合成回帰テスト **5/5 PASS**：父母両ID検証による全兄姉、母方半兄姉、おじ・おば、芝ダ/未来日の排除、取消/中止、母のguard不一致、将来出生馬除外、0走null、血統manifest改ざん拒否。
- 実レースprobeでは、ローカルのPACI固定長抽出に既存レコード配置と互換の**検証用ハーネス**を使用。GitHub実装のcanonical `jrdb_raw.Parser` を通した完全なCLI E2E実行を確認したものではない。GitHubソースへの反映と読み戻しを別途確認する。
- テストのPASSはローカルでの同等実装に対するもの。**GitHub CI上の実行結果ではない**。

## 5. 時点・⑤契約への接続ルール

- `race_date < target_date` の結果除外と、近親の `profile_data_date <= target_date` は実装した。
- しかし研究用世代の関係解決を当時配信済みの関係グラフで再演・認証したわけではない。**`pedigree_temporal_status=RESEARCH_PROFILE_DATE_CHECKED_NOT_HISTORICALLY_REPLAYED` / `prediction_safe=false`。**
- ⑤候補契約に渡す際は、`components.relatives.availability=AS_OF_UNVERIFIED` を維持。未同定は `SOURCE_UNAVAILABLE`。履歴観測があっても「血統的にプラス」と自動判定しない。
- 親族全体を複勝率1つにプールしない。全兄姉・半兄姉・おじおばは別の根拠とし、重複/近縁度と少サンプルを保存する。
- ④は**研究用の血縁取得と条件別実績出力まで実装**。系統ルーツの広域近親、父方近親、複数代先の全血統親族は未対応。

## 6. 再現コマンド

```bash
python horse-racing/brdb/src/run_brdb_relatives_evidence.py \
 --paci /private/PACI261101.zip --race-key 05264b05 \
 --research-generation-root /private/brdb_research_generation_5279af0bd8226cde \
 --analysis-root /private/jrdb_analysis_v1_4_current \
 --output /private/tokyo5_relatives_research.json --years 10

python -m unittest discover -s horse-racing/brdb/tests -p test_brdb_relatives_evidence.py -v
```

PACI/血統Parquet/結果Parquet/全馬JSON個票はGitHubには書き込まず、ソース/合成テスト/集計監査文書のみを正本管理する。
