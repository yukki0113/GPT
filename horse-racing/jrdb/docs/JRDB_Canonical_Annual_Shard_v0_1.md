# JRDB Canonical Annual Shard v0.1

## 1. 目的

中央競馬プロジェクトで、JRDBの確定年次データをPCごとの手動配置から切り離し、RaceNote・PWA・Eval・指数開発が必要に応じて共通利用できる年次SQLite shardを定義する。

本層はRawを置換しない。

```text
JRDB annual Raw ZIP
      |
      v
src/jrdb_raw.py                 # 固定長解釈の正本
      |
      v
src/build_jrdb_canonical.py     # neutral SQLite materialization
      |
      v
jrdb_canonical_YYYY_v0_1.sqlite.zip
      |
      v
Google Drive JRDB Store
      |
      v
jrdb://canonical/YYYY
```

正本の役割は次のように分離する。

- **データ原典 / reproducibility source:** JRDB Raw
- **固定長の読み方の正本:** `src/jrdb_raw.py`
- **通常運用で共有する年次materialization:** Canonical Annual Shard
- **共有artifactの所在正本:** Drive live store manifest

## 2. v0.1 の責務

Canonical Annual Shardは、Common Reader v0.1が返すneutral fieldをSQLiteへ投影する。

対象family:

- BAC
- KYI
- CHA
- CYB
- SED
- SKB
- UKC

ZED/ZKBはSED/SKBとbyte-compatibleであり、年次確定データではSED/SKBを保存する。RaceNote等が「提供済み前走」として扱うかどうかはconsumerのas-of policyで決める。

## 3. 非責務

Canonical builderは次を行わない。

- JRDB固定byte offsetの独自定義
- JRDB codeの日本語label化
- RaceNote向けgrouping/token圧縮
- Eval固有列への変換
- Ability / Edge等の特徴量生成
- 予想ロジック

新しいRaw fieldが必要な場合は、まずCommon Readerへfieldとcharacterization testを追加し、その後Canonical schemaをversion upする。

## 4. schema

schema正本:

`schema/jrdb_canonical_schema_v0_1.sql`

主要table:

- `canonical_build` — schema/parser version、build status、source manifest
- `source_archive` — annual ZIPのkind/year/filename/SHA-256/size/member数/record数
- `bac_race` — BAC neutral race fact
- `kyi_entry` — KYI neutral pre-race horse fact
- `kyi_previous_link` — prev1-5 result/race key
- `kyi_trait` — KYI trait code 1-6
- `cha_workout` — CHA本追切
- `cyb_training` — CYB調教分析
- `sed_result` — SED成績
- `skb_extension` — SKB成績拡張
- `skb_tokki` — 特記code 1-6
- `skb_equipment` — 馬具code 1-8
- `ukc_profile` — UKC horse profile observation

Convenience view:

- `v_pre_race_entry`
- `v_result_full`

## 5. provenance

各source rowには次を保持する。

- `source_id`
- `source_member`
- `record_hash`

`record_hash`はCRLFを除いたrecord bodyのSHA-256とする。これによりPACIのCRLF-inclusive表現とannual Rawを`splitlines()`したbody表現で同一record hashになる。

Raw bytesそのものはSQLiteへ複製しない。再現・監査時は`source_archive`のarchive SHAと`source_member`を使ってRawへ戻る。

## 6. build

```bash
python src/build_jrdb_canonical.py \
  --raw-root /path/to/JRDB/00_raw \
  --year 2024 \
  --db ./jrdb_canonical_2024_v0_1.sqlite
```

`raw-root`は次の双方を受け付ける。

```text
<root>/BAC/BAC_2024.zip
<root>/BAC_2024.zip
```

build後に`ANALYZE`、`VACUUM`、`PRAGMA integrity_check`を実行する。

## 7. 2024 PoC実測

2026-09-06にDrive上の2024 annual Raw実データからv0.1 shardを構築した。

### source records

| kind | records |
|---|---:|
| BAC | 3,454 |
| KYI | 47,181 |
| CHA | 47,181 |
| CYB | 47,181 |
| SED | 47,181 |
| SKB | 47,181 |
| UKC | 47,181 |

子table:

- KYI previous links: 235,905
- KYI trait rows: 283,086
- SKB tokki rows: 283,086
- SKB equipment rows: 377,448

### size / build

- annual Raw ZIP 7種合計: **22,289,870 bytes (~21.26 MiB)**
- Canonical SQLite: **178,450,432 bytes (~170.18 MiB)**
- ZIP transport: **54,815,315 bytes (~52.28 MiB)**
- full build + ANALYZE + VACUUM: **16.89 sec**
- SQLite integrity_check: **ok**

SHA-256:

- SQLite: `45a7cfb22ddf9840460fe6d3a3681ecc255f16c37071c68f2fa939695b53733b`
- ZIP: `02f0d665c9bbe43cfb479c6f627f24cf36e9ee3c08e7013ef1bbed43e3e74166`

lossless Raw-BLOB proxyよりSQLite/ZIPが大きいのは、v0.1ではCommon Reader fieldを列としてmaterializeし、prev/trait/tokki/equipment child rowsと検索indexを持つためである。

### semantic validation

BAC / KYI / CHA / CYB / SED / SKB / UKCから各100件を固定seedで抽出し、Common Reader parse値とCanonical rowをfield-levelで比較した。

- 7 family × 100 = **700 records**
- mismatches: **0**

synthetic回帰は`tests/test_jrdb_canonical_builder.py`で固定する。

### local query benchmark

代表例: 2024-12-28 中山11R / horse id `17104128`。

| query | rows | median |
|---|---:|---:|
| `v_pre_race_entry` 1R | 18 | 0.433 ms |
| `v_result_full` 1R | 18 | 0.648 ms |
| `sed_result` 1頭年内履歴 | 15 | 0.425 ms |

各計測はlocal SQLiteを毎回new connectionで開く条件。通常運用ではDrive transfer/cache resolutionの方が支配的になり得るため、この値だけでRaw直読を全面置換しない。

## 8. Drive Store publication

2024 v0.1 shardは次の論理名でDrive live manifestへ登録済み。

```text
jrdb://canonical/2024
```

物理配置:

```text
JRDB/10_database/canonical/
  jrdb_canonical_2024_v0_1.sqlite.zip
```

statusは`FINAL`。Store manifestはstorage ZIPと展開後SQLiteの双方についてsize/SHA-256を検証する。

Git文書へ個別Drive File IDは固定しない。

## 9. 利用方針

Canonical Annual Shardは共通の**任意高速materialization**であり、全consumerの必須依存にはしない。

- RaceNote単発1R: PACI/Raw直読が十分軽い場合はそのまま利用可能
- 多数レース・多数馬・反復履歴検索: Canonical shardを優先候補にできる
- PWA/指数研究: consumer専用DBをCanonicalから派生させてもよい
- Eval: 現行のRaw直結契約を壊してまでCanonicalへ移行しない

Consumerは物理pathやDrive IDではなく`jrdb://canonical/YYYY`を要求し、Store Resolverが検証済みlocal cacheを返す。

## 10. version policy

v0.1は**Common Reader v0.1が現在対応するfield集合**のcanonical materializationであり、JRDB Raw全byteを無条件に保存する完全lossless DBではない。

Rawは引き続き完全な再生成・監査sourceである。

schema変更時は既存FINAL shardを黙って上書きせず、schema/data version・filename・payload SHAを更新して再publishする。
