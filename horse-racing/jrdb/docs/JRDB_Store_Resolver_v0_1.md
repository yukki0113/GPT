# JRDB Store Resolver v0.1

## 1. 目的

中央競馬プロジェクトの大容量 JRDB artifact を、PCごとの手動配置や個別Drive File ID指定から切り離す。

Consumer は次のような論理名だけを要求する。

```text
jrdb://analysis/current
jrdb://stats/current
jrdb://canonical/2024
```

Store Resolver が外部 manifest を読み、Google Drive上の実体をSHA-256/sizeで検証しながらローカルcacheへ materialize する。

```text
Google Drive JRDB store
      |
      +-- manifest/jrdb_store_manifest_v1.json
      |       |
      |       +-- logical name -> Drive file ID / size / SHA / status
      |
      +-- 10_database / 20_mart / canonical shards
              |
              v
        src/jrdb_store.py
              |
              +-- verified object cache
              +-- optional ZIP materialization
              v
      RaceNote / Eval / PWA / research consumer
```

## 2. Source of truth の区別

本設計では「正本」を2種類に分ける。

1. **データ原典 / reproducibility source:** JRDB Raw / PACI
2. **通常運用で使う共有artifactの所在正本:** Google Drive上のstore manifest

Analysis Lite、Stats Mart、annual Canonical SQLite等はRawから再生成可能な派生artifactだが、通常のconsumerはDrive上のvalidation済みartifactを共有運用の正本として利用してよい。

ローカルファイルはすべてcacheであり、手動管理する正本ではない。

## 3. manifest

live manifestはGitへ置かない。Gitにはschema/exampleだけを保存し、変動するDrive File IDを固定しない。

現在の固定名:

```text
JRDB/manifest/jrdb_store_manifest_v1.json
```

manifest versionは `1.0`。

各artifactは少なくとも次を持つ。

- `logical_name`
- `artifact_type`
- `schema_version`
- `data_version`
- `period_from` / `period_to`
- `status`
- `storage.provider`
- `storage.file_id`
- `storage.filename`
- `storage.size`
- `storage.sha256`
- `payload.compression`
- `payload.member`
- `payload.filename`
- `payload.size`
- `payload.sha256`

Git側exampleは `config/jrdb_store_manifest.example.json`。

## 4. status

通常resolve可能:

- `FINAL` — 確定年次等。immutable運用を想定
- `YTD` — 当年進行中のaccepted artifact
- `PUBLISHED` — publish済み固定artifact

通常resolve不可:

- `CANDIDATE` — validation中。明示的なallow時だけ利用可能

FINAL artifactは同一logical nameの内容を黙って差し替えない。変更が必要ならdata version / SHAを更新し、必要に応じてlogical naming policyを見直す。

## 5. cache

既定cache root:

- Windows: `%LOCALAPPDATA%/JRDB/cache`
- macOS: `~/Library/Caches/JRDB`
- Linux/Actions: `$XDG_CACHE_HOME/jrdb` または `~/.cache/jrdb`

`JRDB_STORE_CACHE` で上書き可能。

保存はcontent-addressedとし、少なくともstorage SHA-256単位で分離する。

```text
cache/
  objects/<storage_sha256>/<stored filename>
  materialized/<logical name>/<payload_sha256>/<payload filename>
```

既存cacheもsize + SHA-256が一致したときだけ再利用する。破損・古い内容は採用しない。

## 6. download / materialization

v0.1 providerは `google_drive`。

Drive download後に必ずstorage size/SHAを確認してからcacheへ原子的にrenameする。

payload compression:

- `none` — downloaded objectをそのまま利用
- `zip` — manifestで指定されたmemberだけを展開し、payload size/SHAを再検証

`extractall()` は使わず、manifest指定memberだけを読み出す。

annual Canonical SQLiteの現行配置は次の形。

```text
storage.filename = jrdb_canonical_2024_v0_1.sqlite.zip
payload.compression = zip
payload.member = jrdb_canonical_2024_v0_1.sqlite
payload.filename = jrdb_canonical_2024_v0_1.sqlite
```

## 7. Python API

```python
from pathlib import Path
from jrdb_store import StoreResolver

resolver = StoreResolver.from_file(Path("jrdb_store_manifest_v1.json"))
analysis = resolver.resolve("jrdb://analysis/current")
stats = resolver.resolve("jrdb://stats/current")
canonical_2024 = resolver.resolve_year(2024)
```

Consumerは返されたPathをその実行中だけ利用し、恒久的なローカル配置場所として記録しない。

## 8. CLI

```bash
python src/jrdb_store.py \
  --manifest ./jrdb_store_manifest_v1.json \
  list

python src/jrdb_store.py \
  --manifest ./jrdb_store_manifest_v1.json \
  resolve jrdb://analysis/current

python src/jrdb_store.py \
  --manifest ./jrdb_store_manifest_v1.json \
  resolve jrdb://canonical/2024 --offline
```

manifest pathは `JRDB_STORE_MANIFEST` でも指定できる。

## 9. RaceNote bridge

P1ではRaceNoteの既存CLI `--analysis` / `--mart` を壊さず残す。

- 明示pathが両方ある場合: 従来どおりそれを利用
- 未指定のartifactがある場合: store manifestから論理名をresolve
  - Analysis: `jrdb://analysis/current`
  - Stats Mart: `jrdb://stats/current`

これにより既存Actionsは明示path互換モードを維持しながら、GPT/PC側ではmanifestを一度解決すれば個別SQLite path指定を省略できる。

## 10. 2026-09-06 Drive manifest

Drive `JRDB/manifest/` の固定名 `jrdb_store_manifest_v1.json` をlive manifestとする。

現在のentry:

- `jrdb://analysis/current` — Analysis Lite v1.2, 2016-2026YTD through 2026-08-23
- `jrdb://stats/current` — Stats Mart v1.1, same data period
- `jrdb://canonical/2024` — Canonical Annual Shard v0.1, 2024 full year, `FINAL`

2024 Canonicalは `JRDB/10_database/canonical/` にZIP transportとして配置し、storage ZIPと展開後SQLiteの双方をmanifestのsize/SHA-256で検証する。

live File IDはGit文書へ固定しない。

2024 Canonicalの実測・validation詳細は `docs/JRDB_Canonical_Annual_Shard_v0_1.md` を正本とする。

## 11. P1 status / next

2026-09-06時点で以下を完了した。

1. Store Resolver / verified local cache
2. RaceNote Analysis/Mart optional Store bridge
3. true Canonical 2024 v0.1 build
4. Drive publication + `jrdb://canonical/2024` `FINAL` 登録
5. BAC/KYI/CHA/CYB/SED/SKB/UKC 各100件、計700件のfield-level comparison mismatch 0
6. synthetic Canonical builder regression test

### Live direct-download E2E

Drive connector経由ではlive manifest、Canonical ZIP metadata、storage size、manifest登録内容まで確認済み。download/cache/materialize/SHA検証のResolverロジックはsynthetic regressionでPASSしている。

このChatGPT実行環境のローカルコンテナは外部DNSが閉じているため、`drive.usercontent.google.com` をResolver自身が直接取得するlive network E2Eだけは未確認。実PCまたはnetwork-enabled Actionsで初回live resolveを行った際に、storage SHA・payload SHA・SQLite `integrity_check` まで確認して本項を更新する。

次はschema contractを固定したうえで、必要な年だけannual shardを拡張する。RaceNote / PWA / Evalのconsumer migrationは一括ではなく、反復アクセスで利益がある経路だけ段階的に行う。

Raw直読が十分速い単発処理まで無理にSQLite化しない。Store Resolverは「SQLite必須化」ではなく、共有artifactの所在・検証・cacheをconsumerから隠す層である。
