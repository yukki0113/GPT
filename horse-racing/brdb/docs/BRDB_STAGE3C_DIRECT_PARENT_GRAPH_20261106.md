# BRDB ③-C — 個体IDで検証された直接親子グラフ（研究用）

Date: 2026-11-06  
Status: **IMPLEMENTED / STAGE3 REGRESSION PASS / INDEPENDENT REAL-PARQUET AUDIT DONE / CANONICAL RUNNER E2E PENDING**  
Target: immutable generation `5279af0bd8226cde`, source cohort 2022–2024 birth, top 50 sire/BMS subjects.

## ③-Bとの契約上の違い

③-Bの`shared_graph.json`は71 nodes / 75 **root→ancestor reachability**である。特に2代・3代の経路は直接の親子辺ではない。

③-Cは`child_person_key → parent_person_key`という**各ステップ1代の直接親子edge**を別成果物にする。証拠のない中間人物のIDを補完しない。元の到達情報からparent edgeを逆算しない。

## ソースの優先順位と設計

- JRDB: `parent_relation.parquet`から`RESOLVED_EXACT`・`RESOLVED_ALIAS`かつ8桁馬IDあり、矛盾なしの直接親子関係のみを採用。
- JBIS: ③-Bの独立監査済み`v0.1`個体対応2頭と、それらの**直接の父母**4件のみを候補とする。親は`JBIS:10桁`のままであり、JRDB8桁IDを捏造しない。
- 同じ子・役割にJRDBとJBISの双方がある場合、JRDB canonical親子辺は維持するが、JBIS別人物への対応を**確認なく同一化しない**。`parallel_unmerged_parent_claims`に独立保存する。
- `v0.2`の3追加対応と③-Bの45件の入口確認は、対応者が多いことと各祖先への**直接の親子辺の個体ID**が確定したことが同義ではないため、現時点で一括昇格しない。
- source time: `AS_OF_UNVERIFIED`、`prediction_safe=false`、`supports_production_cross_detection=false`を固定。
- 父親`sire`と母親`dam`を区別し、循環を禁止。初期の探索深さは各top50根から3エッジ。

## 実装

| 種類 | パス |
|---|---|
| モデル/生成 | `src/brdb_stage3c_direct_parent_graph.py` |
| 実Parquet runner | `src/run_brdb_stage3c_direct_parent_graph.py` |
| 回帰テスト | `tests/test_brdb_stage3c_direct_parent_graph.py` |

`run_brdb_stage3c_direct_parent_graph.py`は元の`pedigree_fact.parquet`、`parent_relation.parquet`、③-B上位50JSONをSHA256照合後に読み、既存`validate_crosswalk`で2頭4件を検証してから研究グラフを生成する。

```bash
python horse-racing/brdb/src/run_brdb_stage3c_direct_parent_graph.py \
  --pedigree /secure/research/generation/pedigree_fact.parquet \
  --relations /secure/research/generation/parent_relation.parquet \
  --top50 /secure/research/stage3b_top50_master_research.json \
  --crosswalk horse-racing/brdb/taxonomy/stage3b_jrdb_jbis_crosswalk_research_v0_1.json \
  --bridge horse-racing/brdb/taxonomy/stage3b_priority4_bridge_candidate_v0_4.json \
  --output /secure/research/stage3c_direct_parent_graph.json
```

## 完了ゲート（③-C）

1. 最新ブランチのStage 3B/3C回帰テスト（新規11件を含む）が0 failures。
2. 固定Parquetの元SHA照合、実データ生成、ノード・親子辺・平行未統合出典の実測、二重生成のバイト一致。
3. 出典がない外部親子エッジ0、名前だけのID昇格0、JRDB/JBISの混合キー0、直接親子サイクル0。
4. 同一祖先への到達候補の例は研究用に出力し、クロスとしては確定しない。
5. 本番`CURRENT`、RaceNote、Review、PWAを変更しない。

本工程の第1段階は「検証済みの直接親子グラフのモデルと生成器」であり、海外の旧祖先すべての個体IDの確定ではない。実データ実行が可能になるまでは工程を**完了**としない。今後の第2段階で未確定5頭、2代10枠・3代40枠、36件の表記差の確認および追加本人crosswalkを一括研究する。

## 初回監査結果（2026-11-06 16時台 JST）

### 正本Parquet実バイトSHA

- `pedigree_fact.parquet`: `1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536` — **一致**。
- `parent_relation.parquet`: `c90482851f91b8f2d99ec88407f4246471d10b38f18163464f88760cb197ff85` — **一致**。
- ③-B上位50JSON: `89d01e2c05af27a929c8398ef9e94660f5f1e442362d458383db6e6a9bd7bdc0` — **一致**。

### 実データの独立検算

同じ元ParquetをDuckDB 1.1.3で読み、③-Cが採用する`RESOLVED_EXACT/RESOLVED_ALIAS`親子辺を、50頭のうちJRDB人物37頭を起点として最大3エッジ辿った。

| 指標 | 独立実測 |
|---|---:|
| JRDB入口個体 | 37 |
| JRDBの一意な直接親子辺 | **42** |
| 既存③-B検証済み（2人4役割）のJBIS直接親子辺 | **4** |
| JRDB/BIS直接親子の同一role衝突 | **0** |
| 合計直接親子辺 | **46** |
| source-native ID別個体ノード | **59** |
| 2つ以上の入口から到達する祖先候補 | **13** |

この検算の正確な位置づけ：**GitHub登録済みの`brdb_stage3c_direct_parent_graph.py`を実行した結果ではない**。別実装の読み取り専用検算であり、③-C本番モジュールのE2E受入条件はまだ未達成。

監査結果ファイルは`stage3c_independent_real_parent_audit.json`としてChatGPT実行環境に保存し、個体同定の追加と推定は行っていない。JBIS直接4辺の前提は既存③-Bの2頭4本監査であり、新たにJBISを閲覧し直したという意味ではない。

### コード回帰実行

PR branch HEAD `abf24ed48879722d571f259f076baddf639ccdd8` に対するstage3回帰テストをGitHub Actionsの正規Data Storage fallbackで実行し、**PASS**。

- [GitHub Actions #42182614944](https://github.com/yukki0113/GPT/actions/runs/42182614944)
- [Issue #2433 実行結果](https://github.com/yukki0113/GPT/issues/2433#issuecomment-6679880856)
- ソースは同一SHAでcheckout、DuckDB 1.1.3、PyArrow 25.0.1。ジョブ結論`success`と成果物登録を確認。

**次に必要**：実Parquetで③-C正本runnerを実行し、上記42+4=46辺／59ノードと一致すること、同じ固定入力で2回出力がバイト一致することを確認。ここまで通過してからPRの取り込み判断を行う。
