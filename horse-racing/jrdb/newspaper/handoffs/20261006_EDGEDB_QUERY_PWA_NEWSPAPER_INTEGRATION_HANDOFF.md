# EdgeDB Query → PWA Newspaper Integration Handoff

Date: 2026-10-06  
Status: IMPLEMENTATION HANDOFF  
Target subsystem: `horse-racing/jrdb/newspaper/` / `horse-racing/jrdb/pwa/`  
EdgeDB query contract: `edgedb-query/v1`  
Production migration: NOT YET APPLIED

## 1. Purpose

PWA新聞の日次生成で、PACIから出走馬を構成する流れの中に新しい共通EdgeDB Queryを自然に組み込みます。

目標は次です。

```
PACI
  -> Newspaper Base / 全出走馬
  -> canonical pre-race runner facts
  -> jrdb_edgedb_query.py
  -> 全出走馬のEdge signal照合
  -> Newspaper Edge adapter
  -> special_memos
  -> day-package.json
  -> PWA
```

PWA/新聞側はEdge条件を再判定しません。

**EdgeDB Queryだけが照合を担当し、Newspaper/PWAは照合済み結果を表示用に投影するconsumerです。**

---

## 2. Current state

現在のNewspaper日次buildは:

`horse-racing/jrdb/src/jrdb_newspaper_day_build.py`

でPACIから全レース・全出走馬を構成します。

Base生成時点では:

```json
"source_status": {
  "edge": {
    "state": "PENDING"
  }
}
```

となり、Edgeは後段で:

- `jrdb_newspaper_edge_adapter.py`
- `jrdb_newspaper_merge_edge.py`

を使ってmergeします。

この「BaseとEdge mergeを分離する」構造は維持します。

変更するのは、**Edge matcher入力の生成経路**です。

旧:

```
PACI
 -> generation-specific Edge matcher
 -> edge_matches.jsonl
 -> Newspaper Edge adapter
 -> merge
```

新:

```
PACI
 -> jrdb_edgedb_query.py
 -> edgedb-query/v1 JSONL
 -> Newspaper Edge adapter
 -> merge
```

---

## 3. New canonical matcher/query

正本:

`horse-racing/jrdb/src/jrdb_edgedb_query.py`

manifest:

`horse-racing/jrdb/config/edgedb/current_manifest.json`

query schema:

`edgedb-query/v1`

current manifest lifecycle:

- v0.2 = `STANDARD`
- v0.3 = `SHADOW`
- v0.4 = `OBSERVE_ONLY`

Newspaper/PWA通常運用では、原則として:

`--profile STANDARD`

を使用します。

これにより、現在の本番表示に使ってよいSTANDARDのみが返ります。

---

## 4. Recommended daily integration flow

### Step 1 — Build Newspaper Base from PACI

既存どおり:

```bash
python horse-racing/jrdb/src/jrdb_newspaper_day_build.py \
  --paci PACI_YYYYMMDD.zip \
  --date YYYYMMDD \
  --analysis <analysis source if required> \
  --output-dir <base_day_dir>
```

この時点で全出走馬の:

- race_key
- race_horse_key
- horse_no
- horse identity

がNewspaper Baseに存在します。

### Step 2 — Run unified EdgeDB Query directly from the same PACI

推奨:

```bash
python horse-racing/jrdb/src/jrdb_edgedb_query.py \
  --manifest horse-racing/jrdb/config/edgedb/current_manifest.json \
  --paci PACI_YYYYMMDD.zip \
  --analysis-root <canonical Analysis root> \
  --profile STANDARD \
  --output-jsonl <work>/edgedb-query.jsonl
```

SQLite compatibility sourceを使う場合は、実装が許す範囲で `--analysis-db` を使用します。

重要:

**Newspaper Baseから馬を1頭ずつmatcherへ渡す必要はありません。**

同じPACIを `jrdb_edgedb_query.py` に1回渡し、その日全体のrunner factsを一括構成・照合します。

これにより:

- source load 1回
- PACI parse 1回
- 全出走馬一括match
- generation-specific matcherの直接呼び出し不要

となります。

---

## 5. Identity join

Edge Query出力とNewspaper Baseのjoin正本は:

1. `race_horse_key`
2. `race_key`
3. `horse_no`

の完全一致です。

Newspaper現行mergeと同じく、近似馬名joinは禁止します。

期待するEdge Queryのrunner key:

```json
{
  "key": {
    "race_date": "2026-10-xx",
    "race_key": "...",
    "race_horse_key": "...",
    "horse_id": "...",
    "horse_no": 7
  }
}
```

Newspaper側はこのidentityを受け取り、既存の:

`race_key + race_horse_key + horse_no`

exact joinを維持します。

---

## 6. Required Newspaper adapter change

現行:

`horse-racing/jrdb/src/jrdb_newspaper_edge_adapter.py`

は旧matcherの `edge_matches` shapeを前提にしています。

このadapterを、`edgedb-query/v1` を受け取れるように拡張してください。

推奨は旧形式を壊さず:

```
load_special_memo_index(...)
  -> legacy matcher row
  -> edgedb-query/v1 row
```

の両方を一定期間受けるcompatibility方式です。

新形式では:

```json
{
  "schema_version": "edgedb-query/v1",
  "key": {...},
  "signals": [...]
}
```

から、表示可能なsignalだけを `special_memos` へ投影します。

---

## 7. STANDARD display policy

通常PWA新聞では `--profile STANDARD` を使うため、原則としてSTANDARDしか入力に来ません。

それでもadapter側でfail-closed guardを持ちます。

通常表示可能:

- `source_lifecycle == STANDARD`
- `production_eligible == true`
- 現行のperformance signal / evidence / presentation条件を満たすもの

通常表示禁止:

- SHADOW
- OBSERVE_ONLY
- production_eligible == false

つまり、query profileとadapter gateの二重防御です。

---

## 8. v0.4 OBSERVE_ONLY handling

v0.4の347件は現在:

`OBSERVE_ONLY`

です。

通常のPWA新聞には表示しません。

ただし研究・デバッグ表示を将来追加する場合は:

```bash
--profile RESEARCH_ALL
```

で取得できます。

その場合も通常 `special_memos` へ混ぜず、たとえば研究用namespace:

```json
"addons": {
  "edge_research": {
    "signals": [...]
  }
}
```

またはdebug専用表示へ分離することを推奨します。

v0.4 OBSERVE_ONLYは:

- positive/negativeの本番シグナルではない
- score加点対象ではない
- mark変更対象ではない
- 単にcohort condition matchである

ことを維持してください。

---

## 9. PWA rendering boundary

PWAブラウザ側:

- Edge matcherを実装しない
- condition comparisonをしない
- manifestを読んでmatcherを再現しない
- ROI/evidenceから独自スコアを作らない

PWAが行うのは:

```
day-package
 -> horse.special_memos
 -> render
```

だけです。

既存 `SYNC_PROVIDER.md` の思想:

> PWAはsource側の条件を再評価しない

をそのまま維持します。

---

## 10. Recommended integrated build shape

将来的にはNewspaper日次生成を以下の1コマンドwrapperにまとめるのが理想です。

例:

`jrdb_newspaper_build_with_edgedb.py`

内部:

```
1. jrdb_newspaper_day_build.build_day()
2. jrdb_edgedb_query query from same PACI
3. Newspaper Edge adapter
4. jrdb_newspaper_merge_edge.merge_edge_day()
5. audit
6. day-package
```

ただし責務は分離したままにします。

wrapperはorchestrationだけを担当し:

- Edge条件判定
- evidence判定
- Newspaper表示条件

を再実装してはいけません。

---

## 11. Preferred final routine

日次PWA新聞作成の最終形:

```
PACI取得
  |
  +-> Newspaper Base build
  |
  +-> EdgeDB Query STANDARD
           |
           v
     edgedb-query/v1
           |
           v
     Newspaper adapter
           |
           v
Base + Edge exact merge
  |
  +-> Eval
  +-> RaceNote prediction
  +-> keibailuka
  +-> independent index
  |
  v
audit
  |
  v
day-package.json
  |
  v
Drive canonical
  |
  v
Newspaper Current Publish
  |
  v
GitHub Pages
  |
  v
PWA
```

EdgeをPACIから自然に生成できるので、今後は「別スレッドでEdge matcher出力を用意してから新聞に渡す」運用を減らせます。

---

## 12. Source status semantics

Edge Query成功 + exact merge成功:

```json
"edge": {
  "state": "READY"
}
```

Edge Queryを実行できなかった:

```json
"edge": {
  "state": "ERROR"
}
```

Edgeがoptional sourceであり、PACI/Baseが成立している場合:

**Edge ERRORだけで新聞日次build全体をHard Stopしない。**

既存Newspaper運用契約を維持します。

---

## 13. Required audit

最低限記録:

- EdgeDB query schema
- query_engine_version
- manifest_revision
- profile
- manifest SHA-256
- PACI SHA-256
- Analysis generation
- total runner rows
- matched runner count
- total signal count
- STANDARD signal count
- non-STANDARD signal count
- Newspaper merged rows
- memo runner count
- memo count
- missing join count
- extra join count
- output day-package SHA-256

通常STANDARD運用で:

`non-STANDARD signal count == 0`

をassertしてよいです。

---

## 14. Acceptance tests

PWA/Newspaper migration前に最低限:

### A. Legacy parity

同じPACI・同じv0.2 STANDARD sourceで:

旧:

`run_jrdb_edge_match_current_v0_2.py`

新:

`jrdb_edgedb_query.py --profile STANDARD`

を比較します。

以下が一致:

- runner key
- matched edge ID
- evidence level
- performance signal
- presentation role
- Newspaper special_memos

### B. Full-day Newspaper parity

既知の日次fixtureで:

旧Edge merge day-package

vs

新EdgeDB Query merge day-package

のEdge以外のfieldがbyte/semantic不変であることを確認します。

Edge表示も現行STANDARDについて同値を要求します。

### C. No research leakage

`--profile STANDARD` で:

- SHADOW 0
- OBSERVE_ONLY 0

を確認します。

### D. RESEARCH_ALL isolation

研究用queryではv0.4が返っても:

- special_memos本番欄へ混入しない
- mark変更なし
- RaceNote prediction変更なし

を確認します。

---

## 15. Files expected to change in implementation phase

主候補:

- `horse-racing/jrdb/src/jrdb_newspaper_edge_adapter.py`
- `horse-racing/jrdb/src/jrdb_newspaper_merge_edge.py`
- optional orchestration wrapper
- Newspaper focused tests
- `horse-racing/jrdb/newspaper/.gpt/WORKFLOW.md`
- `horse-racing/jrdb/newspaper/.gpt/DAILY_WORK_CONTRACT.md`
- `horse-racing/jrdb/newspaper/.gpt/HANDOFF.md`
- `horse-racing/jrdb/newspaper/README.md`

PWA JS側は、`special_memos` shapeを維持できる限り変更不要が理想です。

---

## 16. Migration rule

consumer migration完了後は、Newspaper日次運用からgeneration-specific matcherの直接実行を外します。

正本:

```
jrdb_edgedb_query.py
+ current_manifest.json
```

compatibility only:

```
run_jrdb_edge_match_current_v0_2.py
jrdb_edge_matcher_v0_2.py direct consumer use
```

既存matcher module自体は内部adapterとして残して構いません。

---

## 17. Important non-goals

このPWA連携で行わないこと:

- v0.4を本番昇格しない
- Edge scoreを新規作成しない
- PWAで条件判定しない
- RaceNote予想ロジックを変更しない
- SHADOW/OBSERVE_ONLYを通常新聞へ表示しない
- 馬名近似joinを導入しない
- Edge optional failureをPACI/Base hard stopへ昇格しない

---

## 18. Implementation target

最終的にPWA新聞担当へ期待する運用は:

> PACIを渡して新聞を作ると、そのPACIの全出走馬が自動で最新EdgeDB manifestへ照合され、現在本番表示可能なEdgeだけが `special_memos` として自然に新聞へ載る。

これを標準状態とします。
