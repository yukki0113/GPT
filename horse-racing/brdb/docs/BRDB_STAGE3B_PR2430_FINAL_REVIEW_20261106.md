# PR #2430 — ③-B 最終レビュー：祖先到達表と親子グラフの契約境界

Date: 2026-11-06  
PR: https://github.com/yukki0113/GPT/pull/2430  
Scope: **research-only Stage3B**, no production/current mutation.

## レビュー対象と判定

1. 実入力の正本照合と50頭一括調査：**PR監査報告上は達成**。元CSV・50頭JSON・研究Parquet SHA一致、世代1/2/3に対して100/100・190/200・360/400の名前観測。出典資料の過去時点可用性は未検証。
2. JRDB 8桁IDとJBIS 10桁IDの名前空間分離：**研究実装で維持**。1/2/3代のJRDB pathは36/10/0、JBIS source-qualified pathは6/20/3。個体ID未確定・表記差はそのまま残す。
3. 父/母父別の登録入口：上位50対象で父6,155/12,018（51.21%）、母父4,988/12,018（41.50%）。出典確認45入口に限ると父5,539/12,018、母父4,704/12,018。**出走回数や実際の条件別適性とは別母集団**。
4. 研究用`shared_graph.json`：**直接親子edge tableではない**。50頭のrootと確認済み祖先を`path`（S/D列、長さ1～3）で結んだ「祖先への到達関係」。71ノード、75 `root→ancestor` reachability recordsは**75本の直接親子辺ではない**。特に長さ2/3のパスから中間人物を復元してよいとは限らない。
5. 同一祖先のクロス検出／遺伝的近交計算：**未承認／未実装**。根拠付きの直接の父母（親子）エッジを別に構築し、同一個体判定、閉路防止、各S/Dステップのsource provenance、独立したcross detector testsが必要。
6. 本番への非干渉：PRの変更ファイルは`horse-racing/brdb/`のsrc、test、taxonomy、docsのみ。CURRENT pointer、⑤採点、RaceNote、PWA、新聞、workflowを変更しない。PRはdraftを維持。

## 修正した契約

- `src/audit_brdb_stage3b_top50_sources.py` の`shared_graph.json` に、`schema_version=brdb-stage3b-reachability-v0.1`、`graph_kind=ROOT_TO_ANCESTOR_REACHABILITY`、`direct_parent_edge_count=0`、`supports_cross_detection=false`、`prediction_safe=false`を明示。旧フィールド`nodes`/`paths`は互換のまま。
- `src/brdb_stage3b_reachability_contract.py`は、ID名前空間、参照先ノード、S/D経路、IDとsource statusの一致、重複経路、as-of禁止条件をfail-closedに検証。
- 生成モジュールは監査時にこの契約を検証し、summaryへ`graph_contract_validation`を追記。
- `tests/test_brdb_stage3b_reachability_contract.py`に9件の回帰テストを追加。

## バックログとして分離するもの

- source人物対応未確認5頭：リアルスティール／シンボリクリスエス／モズアスコット／タワーオブロンドン／ヘニーヒューズ。
- 2代前の名前欠損10枠、3代前40枠、JRDB/JBISの表記差・事実矛盾未確定36枠。
- **直接親子グラフ**（typed edge `child_person_key, parent_person_key, role, source, source_date/asof_status, identity_confidence`）の別途構築と検証。母母DDは取得できた場合だけ、父と母父優先の方針を変えない。
- source historical as-ofの追認。情報が出走前に入手可能だったか不明なまま評価・予想に投入しない。

## 取り込み判定

**研究用①祖先資料監査としては受け入れ可能な範囲**。ただしPRを`ready`／mergeする前に、今回変更したreachability contractの**Python回帰テスト再実行**と、既存入力による**変更後の正本監査runner再実行**、全件の出力差分（今回追加したcontract field以外の名寄せ・coveragesが変わらないこと）を確認する。

外部データ調査と本番採点導入は、今回の取り込み条件には含めない。取り込み後の残件を静的研究台帳に置く。

この文書はユーザーの意思に代わってPRをmergeする許可ではなく、監査上の受け入れ条件を定義する。
