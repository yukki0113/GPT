# BRDB ③-C — 個体IDで検証された直接親子グラフ（研究用）

Date: 2026-11-06  
Status: **IMPLEMENTED / TEST AND REAL-PARQUET AUDIT PENDING**  
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
