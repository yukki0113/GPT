# RaceNote Archive Design v0.1

RaceNote Archive は、過去レースのRaceNoteを大量・反復取得する際にannual Rawを毎回走査しないための派生データ層です。

本設計は2026-08-27時点のRaceNote production v1.0を前提とします。

## 1. 目的

現在のRaceNote request contractは維持したまま、`past` requestのbase取得を高速化します。

```text
user / GPT
  -> racenote_request.py
  -> past: RaceNote Archive preferred
  -> base RaceNote v0.2
  -> Analysis Lite / Stats Mart enrichment
  -> final RaceNote v1.0
```

ArchiveはRaw/Coreの代替正本ではありません。

```text
canonical Raw ZIPs / Core
  = audit / rebuild / source truth

RaceNote Archive
  = historical base RaceNote delivery cache

Analysis Lite / Stats Mart
  = as-of-safe history/statistics enrichment
```

## 2. 非目的

初期Archiveでは以下を行いません。

- prediction logicを保存しない
- final RaceNote v1.0を保存しない
- Analysis Lite / Stats Mart集計を焼き込まない
- target race resultを保存しない
- Raw/Coreを置換しない
- 海外履歴等の欠損を推測補完しない

## 3. Archiveへ保存するもの

Archiveへ保存する単位は **base RaceNote v0.2の1レース1JSON** とします。

理由:

1. v1.0のAnalysis/Mart enrichmentはas-of計算や集計仕様が更新され得る。
2. final v1.0をArchiveへ固定すると、enrichment変更のたびに全過去RaceNoteを再生成する必要がある。
3. base v0.2を保存すれば、現在のproduction enrichment engineから常に現行v1.0を生成できる。
4. PACI/annual Rawからの重い再構成処理だけをArchiveで省略できる。

Archive row内のbundleは `racenote_jrdb.py` が生成するbase schema v0.2を保持し、Archive独自項目をJSON内部へ注入しません。Archive provenanceはSQLite側のmetadataで管理します。

## 4. Shard方式

初期production候補は **1暦月 = 1 SQLite shard** とします。

ファイル名:

```text
jrdb_racenote_archive_YYYYMM_v1_0.sqlite
```

例:

```text
jrdb_racenote_archive_202508_v1_0.sqlite
```

### 年次1ファイルを採らない理由

1R取得でもremote storageから1年分をdownloadする必要があり、通常requestには重い。

### 日次1ファイルを採らない理由

ファイル数が多くなり、Drive探索・manifest・世代更新が煩雑になる。

### 月次の利点

- 単発requestでは対象月1 shardだけ取得すればよい
- 数週間〜数か月のbacktestではshardをcacheして再利用できる
- 1年一括処理でも最大12 shardで管理できる
- shard内はSQLite indexで日付・場・Rを即時lookupできる
- closed monthはimmutable artifactとして扱いやすい

将来、長期間bulk deliveryが必要なら「12個の月次shardをまとめた年次transport ZIP」を追加してもよい。ただしそれは搬送用であり、Archiveの論理正本単位は月次shardのままとします。

## 5. SQLite schema

機械可読schema draftは `schema/racenote_archive_schema_v1_0.sql` とします。

主要table:

```text
archive_meta
  shard全体のversion / month / converter / coverage / compression

source_input
  PACIまたはannual Raw inputのfilename / SHA-256 / role

race_bundle
  1 race = 1 compressed base RaceNote JSON
```

### race_bundle primary key

```text
(race_date, venue_code, race_no)
```

`race_key` もUNIQUEとします。

RaceNote JSONをhorse単位などへ正規化しません。ArchiveはRaceNoteの検索・搬送層であり、RaceNote schemaの内部変更とArchive DB schemaを極力分離するためです。

## 6. Bundle compression / hash

bundle JSONはUTF-8 bytesをPython標準 `zlib` で圧縮しBLOB保存します。

```text
compression = zlib
```

外部依存を増やさず、SQLite 1ファイル内で十分な圧縮を得ることを優先します。

各rowは2種類のhashを保持します。

### bundle_sha256

保存前のJSON bytesそのもののSHA-256。

用途:

- BLOB decompress後の破損検知
- artifact内部integrity確認

### semantic_sha256

JSONをparseし、volatile metadataだけを除外したcanonical JSONのSHA-256。

初期除外対象:

```text
metadata.generated_at
```

用途:

- rebuild時刻が異なるArchive同士の意味比較
- Raw fallback / PACI direct pathとの回帰比較

除外項目はArchive schema/version単位で固定し、勝手に追加しません。

## 7. Source provenance

shardは生成元を追跡可能にします。

`archive_meta` には少なくとも以下を保持します。

```text
archive_schema_version = 1.0
base_schema_version    = 0.2
target_month           = YYYYMM
converter_git_sha      = racenote_jrdb.pyを実行したGit commit
compression            = zlib
coverage_start
coverage_end
race_count
built_at
```

`source_input` には使用した外部sourceを保存します。

例:

```text
PACI260509.zip
BAC_2025.zip
KYI_2025.zip
CHA_2025.zip
CYB_2025.zip
SED_2024.zip
SED_2025.zip
SKB_2024.zip
SKB_2025.zip
```

各inputについて `source_type / source_period / filename / sha256 / role` を記録します。

認証情報・Drive URL・Drive File IDはArchiveにもGitにも保存しません。

## 8. Build path

### 8.1 2026年以降

PACIが存在する日付はPACIを直接base converterへ渡します。

```text
PACIyymmdd.zip
  -> racenote_jrdb.py
  -> base RaceNote v0.2 bundles
  -> monthly Archive shard
```

Archiveは事前情報bundleを保存するため、対象日結果は入力しません。

### 8.2 2025年以前

annual RawからPACI-equivalent inputを再構成します。

```text
annual BAC/KYI/CHA/CYB
  + KYI prev1-5が参照するSED/SKB
  -> daily PACI-equivalent
  -> racenote_jrdb.py
  -> base RaceNote v0.2 bundles
  -> monthly Archive shard
```

重要:

- target raceのSED/SKBをJOINしない
- KYIに明示されたprevious result keyだけをZED/ZKBへ採用する
- target year Rawを日付ごとに再走査せず、Archive builder内で一度index化して複数race/dateへ再利用する

現在の1request用Raw fallbackの安全性は維持しつつ、Archive buildではyear-wide indexingにより量産効率を上げます。

## 9. Initial coverage

初期Archive coverageは、production Analysis Liteの通常利用期間に合わせて **2016年以降** を第一対象とします。

```text
Phase 1: 2016-2025 annual Raw build
Phase 2: 2026 YTD PACI build
Phase 3: in-season incremental append/rebuild
```

2016年RaceNoteのrecent historyが2015年以前を参照する場合、必要なSED/SKBはKYI previous result keyに従って参照します。

Archive自体は将来2010年等へ拡張可能ですが、Analysis Lite / Stats Mart enrichment coverageと組み合わせて利用可能期間を判断します。

## 10. Router integration

user-facing request contractは変更しません。

```text
date  required
venue optional
race  optional (requires venue)
```

過去requestのbackend優先順位を次へ変更します。

```text
past
  1. RaceNote Archive shardがavailable / validated
       -> archive
  2. Archive unavailable
       -> current safe fallback
          2026+ : PACI
          <=2025: annual Raw reconstruction

current / future
  -> PACI
```

Archive障害や未整備月があっても、既存fallbackを残すためrequest contractは壊れません。

### CLI候補

```text
--archive-dir PATH
--archive-required
```

- `--archive-dir`: shard cache/root。未指定なら既存backendのみ。
- default: Archiveがあれば使用し、無ければfallback。
- `--archive-required`: bulk backtest等で意図せずannual Raw fallbackへ落ちることを防ぐ内部運用option。

通常ユーザーにはこれらを指定させません。

## 11. Archive lookup

request dateからshard名を決定します。

```text
2025-08-24
  -> jrdb_racenote_archive_202508_v1_0.sqlite
```

race scope:

```sql
WHERE race_date=? AND venue_code=? AND race_no=?
```

venue scope:

```sql
WHERE race_date=? AND venue_code=?
ORDER BY race_no
```

all scope:

```sql
WHERE race_date=?
ORDER BY venue_code, race_no
```

取得後:

1. zlib decompress
2. `bundle_sha256` verify
3. JSON parse
4. base schema version verify
5. temporary base bundleとして既存 `racenote_history_enrichment.py` へ渡す
6. final RaceNote v1.0を生成

Archive read pathにprediction logicを入れません。

## 12. GitHub Actions / external storage

大容量Archive shardはGit管理しません。

external storageでは固定命名規約を使用します。

```text
jrdb_racenote_archive_YYYYMM_v1_0.sqlite
jrdb_racenote_archive_manifest_v1.json
```

manifestは少なくとも以下を持ちます。

```json
{
  "archive_schema_version": "1.0",
  "base_schema_version": "0.2",
  "shards": [
    {
      "month": "202508",
      "filename": "jrdb_racenote_archive_202508_v1_0.sqlite",
      "sha256": "...",
      "bytes": 0,
      "race_count": 0,
      "validation": "PASS"
    }
  ]
}
```

GitへDrive URL / File IDを固定しません。
GPT/Workflowは対象monthの最新compatible / validation PASS shardを外部storageから解決します。

`[RACENOTE_REQUEST]` Issue経路では、将来内部fieldとして `archive_url` を受けられるようにしてもuser-facing contractは変更しません。

## 13. Update policy

### closed month

validation PASSしたclosed month shardはimmutableとして扱います。

converter/schema修正で再生成が必要な場合は、同じ月を新しいarchive generationとして全件rebuildし、manifestのlatest compatible artifactを差し替えます。

### current month

PACI追加時に月次shardを再生成またはreplaceできます。

同一shard内でconverter versionを混在させません。converterが変わった場合はshard全体をrebuildします。

## 14. Validation contract

Archive shardをPASSとする最低条件:

1. `PRAGMA integrity_check = ok`
2. target month外のrace row = 0
3. duplicate primary key = 0
4. duplicate race_key = 0
5. 全BLOB decompress成功
6. 全row `bundle_sha256`一致
7. 全bundle `schema_version = 0.2`
8. bundle race date/venue/raceとindex columnsが一致
9. `recent_runs` のrace dateがtarget date未満
10. target race resultの混入なし
11. source manifest SHA-256が記録済み
12. expected race countとの照合

expected race countはAnalysis Liteのtarget date/month race keyを参照して監査してよいが、Archive base JSONへAnalysis result値を混入させません。

## 15. Regression / PoC plan

実装時は3段階で確認します。

### A. 1レースsemantic equality

既存検証済みraceを使います。

- 2025-11-30 東京12R ジャパンカップ
  - annual Raw reconstruction由来
- 2026-05-09 京都11R 京都新聞杯
  - PACI由来

比較:

```text
current direct/fallback base
vs
Archive base
```

`metadata.generated_at` を除くsemantic hash一致を必須とします。

さらにproduction enrichment後のfinal v1.0についても意味差分0を確認します。

### B. 1か月full build

2025年の1か月を全race buildし、

- race count
- all / venue / race scope lookup
- duplicate 0
- leakage 0
- hash 100% PASS

を確認します。

初回候補は、既にRaceNote検証資産がある2025-08とします。

### C. performance comparison

同じ過去1R requestで、

```text
annual Raw fallback
vs
Archive local lookup
```

を比較します。

最低限記録する値:

- required external files
- downloaded bytes
- base取得時間
- total request時間
- final bundle bytes
- semantic equality

固定の性能閾値はPoC結果を見てから決めます。

## 16. Failure / fallback policy

Archiveを無条件に信用しません。

以下ではArchive row/shardを使用せずfallbackします。

- integrity_check failure
- archive/base schema mismatch
- target month mismatch
- requested race missing
- BLOB decompress failure
- hash mismatch
- JSON/index key mismatch

`--archive-required` の場合はfallbackせずfail-fastします。

通常requestでは既存PACI/Raw safe backendへfallbackします。

## 17. Implementation phases

### Phase A - schema / local builder PoC

- `schema/racenote_archive_schema_v1_0.sql`
- `src/build_racenote_archive.py`
- monthly shard generation
- validation report

### Phase B - archive reader

- `src/racenote_archive.py`
- date/venue/race lookup
- decompress/hash/schema validation

### Phase C - router integration

- `racenote_request.py` past backend priorityへArchive追加
- existing fallback維持
- request manifestへactual base backend / archive provenance追加

### Phase D - GitHub Actions delivery

- target month shard resolver/download
- `[RACENOTE_REQUEST]` pathでArchiveを利用
- artifact回帰

### Phase E - historical population

- 2016-2025 monthly shards
- 2026 YTD
- external manifest生成
- full audit

## 18. Design decision summary

初期RaceNote Archiveは以下を正式候補とします。

```text
logical role       historical base delivery cache
stored schema      RaceNote base v0.2
archive schema     v1.0
shard              monthly
container          SQLite
payload            zlib-compressed 1-race JSON BLOB
lookup             date + venue_code + race_no
provenance         source SHA-256 + converter Git SHA
final output       current production RaceNote v1.0 enrichment
fallback           existing PACI / annual Raw path
source truth       Raw/Core remains authoritative
```

この境界を守ることで、Archiveは高速化だけを担当し、RaceNote prediction/data semanticsを増やしません。
