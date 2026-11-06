# BRDB ③-B 継続：JRDB↔JBIS個体クロスウォークと共有祖先経路の伝播監査

Date: 2026-11-06  
Status: **2 MULTI-GUARD RESEARCH IDENTITY MATCHES / 4 DIRECT + 22 TRANSITIVE HYBRID PATHS / 22 NOT YET BRIDGED / NO JRDB ANCESTOR-ID INVENTION**

## 0. 今回の結論

③-B優先4祖先の上位50種牡馬からの名前観測48経路について、個別子孫のJBIS出典照合は前回**48/48**まで済んでいる。今回は別の検証軸として、**正式JRDB子孫馬IDとJBIS個体IDの対応を複数の独立項目で検証**し、JRDBの既存canonical親子エッジを介した外部祖先IDへの到達を調べた。

- **ディープインパクトとキングカメハメハの2頭**について、JRDB研究世代の実`pedigree_fact.parquet`をDuckDB 1.1.3で直接確認し、JBIS個別ページおよびJRAの個別馬資料の生年月日・性別・父母と対応させた。JBIS/JRA双方の出典URLを同定記録に保存。
- **2頭のS/D直接親子経路は4本**。祖先4頭（サンデーサイレンス、ウインドインハーヘア、キングマンボ、マンファス）はJBIS固有IDを維持し、**JRDB公式祖先IDは未解決**。
- 同じ2頭へ`parent_relation`の**JRDB canonical馬IDで到達できる11種牡馬**に対し、末端の外部S/Dを接続できる経路を**22本**実際の50頭マスタから検出した。
- よって**外部祖先IDまで研究用のハイブリッド出典連鎖で確認できる経路は26/48（54.17%）**、未接続22/48（45.83%）。13種牡馬にまたがる。
- **これは公式JRDB祖先IDの第1～3世代充足率ではない**。既報の「JRDB正式ID到達 1代36/100、2代10/200、3代0/400」は**不変**。今回の26件はJRDB上の子孫ID→確認済みJBIS上の旧祖先IDという**複合provenanceの到達**。
- 残る上位50対象のJRDB↔JBIS本人ID対応29件は**未承認**。将来の一意ID確証を得るまで自動昇格させない。

## 1. 独立した出典とガード

### ディープインパクト

- JRDB 8桁: `02100816`。対象研究世代で確認した`horse_name=ディープインパクト`、`birth_date=20020325`、`sex_code=1`、父`サンデーサイレンス`（1986）、母`ウインドインハーヘア`（1991）、父系コード`1206`。
- JBIS 個体ID: `0000742976`。出典 https://www.jbis.or.jp/horse/0000742976/ （生年月日・父母名・性別、父母の生年）。
- 別系統の独立一次資料: JRA「ディープインパクト」 https://www.jra.go.jp/gallery/3minmeiba/horse31/ 。
- 本人ID研究用照合結果: `RESEARCH_MULTI_GUARD_VERIFIED`。**JRDB ID=JBIS IDではなく、同一個体に対する別名前空間の対応**。

### キングカメハメハ

- JRDB 8桁: `01103460`。研究世代で確認`horse_name=キングカメハメハ`、`birth_date=20010320`、`sex_code=1`、父`キングマンボ`（1990）、母`マンファス`（1991）、父系コード`1503`。
- JBIS 個体ID: `0000729458`。出典 https://www.jbis.or.jp/horse/0000729458/ 。
- 別系統の独立一次資料: JRA「競馬の殿堂：キングカメハメハ」 https://www.jra.go.jp/gallery/dendo/horse36/ 。
- 本人ID研究用照合結果: `RESEARCH_MULTI_GUARD_VERIFIED`。

各馬に対し氏名・**完全な生年月日**・性別・父母名・父母生年・JRDB正式系統コードを内部照合した。**出生年だけ・馬名だけの一致で他の29頭を承認しない**。外部出典ではコード自体が公式JRDBコードであることを証明するわけではなく、そのコードはJRDB血統factを正本とする。

JRDBソース世代：`5279af0bd8226cde`、`pedigree_fact.parquet` SHA256 `1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536`。静的研究用データであることから**歴史的レース前に参照可能だったか未確認**、`AS_OF_UNVERIFIED`。

## 2. 2頭からの伝播

以下は、対象種牡馬自身からの経路。先頭の`S`=父、`D`=母であり、出走馬が当該種牡馬の産駒ならさらに先頭`S`を付ける必要がある。

| JRDBが個体IDで確認できる中間種牡馬 | 主な接続例 | ハイブリッド経路数 |
|---|---|---:|
| ディープインパクト（root） | `S` Sunday Silence / `D` Wind in Her Hair | 2 |
| キングカメハメハ（root） | `S` Kingmambo / `D` Manfath | 2 |
| キズナ、シルバーステート、リアルスティール、サトノダイヤモンド、コントレイル、ミッキーアイル | 中間`S` Deep Impact → `SS` Sunday Silence / `SD` Wind in Her Hair | 12 |
| ロードカナロア、ルーラーシップ、レイデオロ、リオンディーズ | 中間`S` King Kamehameha → `SS` Kingmambo / `SD` Manfath | 8 |
| サートゥルナーリア | 中間`SS` King Kamehameha → `SSS` Kingmambo / `SSD` Manfath | 2 |
| **合計** | **2 root + 11 descendant種牡馬** | **26** |

- 同名があるだけで伝播していない。上位50マスタに**JRDB解決済みの中間本人8桁ID**があり、親子経路にS/Dを連結し、得られた最終パスと祖先名が**既存の出典付き48観測経路に一致**した場合のみ採用。
- **祖先の外部個体IDは `JBIS:...` のまま**。`canonical_jrdb_ancestor_horse_id=null` を維持。
- 父/母父からの自動実レース分析、血統クロス確定、⑤への加点、PWA・RaceNoteへの配信は禁止。

## 3. 未解決22経路の次優先

新たな人物同定・共有親IDの照合を始める対象（上位50中の延べ登場枠数で優先）：ダイワメジャー（380）、ハーツクライ（374）、エピファネイア（349）、サートゥルナーリア（299）、オルフェーヴル（292）、レイデオロ（228）、ルヴァンスレーヴ（227）、キタサンブラック（226）など。

**未解決22経路は資料未確認ではない**（JBISの血統出典は48/48）。現段階では「JRDBで同定した子孫本人から外部祖先本人への**中間人物同定済みチェーンがつながっていない**」という意味。次はこれら子孫に対し、子孫本人の完全な生年月日・性別・父母名と対応JBISページを一意に照合する。独立出典と矛盾チェックを全件で実施する。

## 4. 検証したこと・未実行のこと

- **実行済み**：研究ParquetのSHA一致、2頭のJRDB sourceプロフィールが完全なガード8項目で一致することのDuckDB実測。独立ローカルPythonスクリプトで上位50研究JSON固定SHAを検証し、2起点×2親 + 11子孫×2親=**26経路**、残り22経路、祖先本人JRDB ID追加0件を実計測。
- **GitHubにコミット**：`taxonomy/stage3b_jrdb_jbis_crosswalk_research_v0_1.json`、`src/brdb_stage3b_identity_crosswalk.py`、`src/run_brdb_stage3b_crosswalk_audit.py`、`src/brdb_stage3b_hybrid_propagation.py`、`tests/test_brdb_stage3b_identity_crosswalk.py`（11件）、`tests/test_brdb_stage3b_hybrid_propagation.py`（6件）。
- **未実行**：GitHubに登録したこれらPythonモジュールそのものの回帰テスト17ケースと、正本runnerを実際に呼ぶE2E。ローカル実証がGitHubモジュールの実行合格を意味するわけではない。コミットの読み戻しと構造整合チェックは別途行う。
- すべて静的研究レジストリ。**BRDB CURRENT、固定レビュー、⑤統合候補schema、RaceNote、PWA、Newspaper、本番workflowは変更しない**。

## 5. 再現の入口

生成済み上位50研究JSONの固定SHA：`89d01e2c05af27a929c8398ef9e94660f5f1e442362d458383db6e6a9bd7bdc0`。GitHub正本コードはこの**同一ローカル研究JSON**を入力とし、元JRDB Parquetプロフィールをguardする。

```bash
python horse-racing/brdb/src/run_brdb_stage3b_crosswalk_audit.py \
  --pedigree /path/to/generation/pedigree_fact.parquet \
  --crosswalk horse-racing/brdb/taxonomy/stage3b_jrdb_jbis_crosswalk_research_v0_1.json \
  --bridge horse-racing/brdb/taxonomy/stage3b_priority4_bridge_candidate_v0_4.json \
  --output /tmp/stage3b_person_crosswalk_audit.json

python -m unittest discover -s horse-racing/brdb/tests \
  -p 'test_brdb_stage3b_*crosswalk.py' -v
```

また`brdb_stage3b_hybrid_propagation.audit_from_files`に元上位50JSON・上記2辞書・`run_...audit`のsourceプロフィールを渡せば、研究用ハイブリッドパス26経路を厳密なfail-closedで抽出する。ただし正本への公開/差替えは行わない。
