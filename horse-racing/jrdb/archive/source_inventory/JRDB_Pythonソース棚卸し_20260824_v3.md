# JRDB Pythonソース棚卸し 2026-08-24 v3

## 0. 結論

Git移行対象の主要Python群は、現時点でほぼ特定済み。
Core Builder v1.1.2は元成果物が見つからなかったものの、過去データ取得スレッド側で再生成・実行テスト済み版を保存済みのため、
以後はその再生成版を現行正本として扱う。

## 1. 現行（Gitの src/ 相当）

| モジュール | 用途 | README/依存物 | 判定 |
|---|---|---|---|
| fetch_jrdb_paci.py | JRDB PACI前日一括ZIP取得 | README_fetch_jrdb_paci.md / requirements_jrdb_paci.txt または現行版README記載の依存 / .env.example / .gitignore | 現行 |
| racenote_jrdb.py | PACI ZIP→RaceNote JSON v0.2系 | README_racenote_jrdb_v0.2.md / CHANGELOG_v0.2.md / jrdb_codebooks.json / RaceNote_v0.2.2_information_representation_change_20260821.md | 現行 |
| racenote_jrdb_pipeline.py | PACI取得→RaceNote 1R JSON生成ラッパー | fetch_jrdb_paci.py / racenote_jrdb.py | 現行 |
| generate_jrdb_codebooks.py | JRDB公式 TOKKI/ASHIMOTO→jrdb_codebooks.json生成 | 原本_tokki_code / 原本_ashimoto_code / jrdb_codebooks.json | 現行補助 |
| fetch_jrdb_history.py | 年次ZIP・2026以降単日ZIP取得 | README_fetch_jrdb_history.md / jrdb_history_fetch_config.json | 現行 |
| build_jrdb_core.py | JRDB Raw ZIP群→Core SQLite構築 | README_build_jrdb_core.md / jrdb_core_schema_v1.sql / jrdb_core_config.json | 現行 v1.1.2（再生成・実行テスト済み版を正本） |
| audit_jrdb_core_v1_1_1.py | Core Builder監査 | v1.1.2 audit md/json 等 | 現行監査候補 |

## 2. Legacy / PoC

| モジュール | 用途 | 扱い |
|---|---|---|
| racenote_jrdb_parser.py | RaceNote JRDB初期PoC | archive |
| build_jrdb_history_2025_poc.py | 2025年次ZIP→SQLite初期PoC | archive |
| build_jrdb_core.py 初版 | Core Builder v1 | archive |
| build_jrdb_core(1).py | Core Builder v1.1 | archive |
| build_jrdb_core(2).py | Core Builder v1.1.1 | archive |
| audit_jrdb_core_v1_1.py | Core v1.1監査 | archive |

## 3. 現行モジュールの依存関係

### PACI→RaceNote
racenote_jrdb_pipeline.py
  ├─ fetch_jrdb_paci.py
  └─ racenote_jrdb.py
       └─ jrdb_codebooks.json
            └─ generate_jrdb_codebooks.py
                 ├─ 原本_tokki_code
                 └─ 原本_ashimoto_code

### History→Core
fetch_jrdb_history.py
  └─ 00_raw_local/<TYPE>/*.zip

build_jrdb_core.py
  ├─ 00_raw_local/<TYPE>/*.zip
  ├─ jrdb_core_schema_v1.sql
  └─ jrdb_core_config.json

audit_jrdb_core_v1_1_1.py
  └─ build_jrdb_core.py の生成SQLite

## 4. docs / config / schema としてGit保存推奨

### docs
- README_fetch_jrdb_paci.md
- README_racenote_jrdb_v0.2.md
- CHANGELOG_v0.2.md
- RaceNote_v0.2.2_information_representation_change_20260821.md
- README_fetch_jrdb_history.md
- README_build_jrdb_core.md（v1.1.2再生成版に対応するものを正本）
- 整理版_JRDB_固定長データ定義.md
- 整理版_JRDB_マスタコード定義.md
- 整理版_JRDB_ファイル相関・キー定義.md

### config / generated master
- jrdb_codebooks.json
- jrdb_history_fetch_config.json
- jrdb_core_config.json

### schema
- jrdb_core_schema_v1.sql

## 5. Gitへ入れないもの

- jrdb_secret.py
- .env（実値）
- JRDB会員ID/パスワードを含むファイル
- Raw ZIP
- SQLite DB
- *.part
- 実行ログ
- fetch_manifest.jsonl / fetch_summary.json 等の実運用生成物（必要なら samples/ に匿名化した例だけ置く）

## 6. 推奨リポジトリ構成案

```text
jrdb/
├─ src/
│  ├─ fetch_jrdb_paci.py
│  ├─ racenote_jrdb.py
│  ├─ racenote_jrdb_pipeline.py
│  ├─ generate_jrdb_codebooks.py
│  ├─ fetch_jrdb_history.py
│  ├─ build_jrdb_core.py
│  └─ audit_jrdb_core_v1_1_1.py
├─ config/
│  ├─ jrdb_codebooks.json
│  ├─ jrdb_history_fetch_config.json
│  └─ jrdb_core_config.json
├─ schema/
│  └─ jrdb_core_schema_v1.sql
├─ docs/
│  ├─ README_fetch_jrdb_paci.md
│  ├─ README_racenote_jrdb_v0.2.md
│  ├─ CHANGELOG_v0.2.md
│  ├─ RaceNote_v0.2.2_information_representation_change_20260821.md
│  ├─ README_fetch_jrdb_history.md
│  ├─ README_build_jrdb_core.md
│  ├─ 整理版_JRDB_固定長データ定義.md
│  ├─ 整理版_JRDB_マスタコード定義.md
│  └─ 整理版_JRDB_ファイル相関・キー定義.md
├─ archive/
│  ├─ racenote_jrdb_parser.py
│  ├─ build_jrdb_history_2025_poc.py
│  └─ core_builder/
│     ├─ v1/
│     ├─ v1.1/
│     └─ v1.1.1/
├─ .env.example
├─ .gitignore
└─ README.md
```

## 7. 現時点で個別回収が必要なもの

File Library上で存在確認済みでも、このチャットのローカル作業領域へ直接バイト回収できていないものがあるため、
ZIP作成前に以下を正本ファイルとして揃える。

1. v1.1.2 再生成済み build_jrdb_core.py
2. それに対応する README_build_jrdb_core.md
3. jrdb_core_schema_v1.sql
4. jrdb_core_config.json
5. audit_jrdb_core_v1_1_1.py
6. racenote_jrdb.py
7. racenote_jrdb_pipeline.py
8. generate_jrdb_codebooks.py
9. jrdb_codebooks.json
10. fetch_jrdb_paci.py
11. README_fetch_jrdb_paci.md
12. fetch_jrdb_history.py
13. README_fetch_jrdb_history.md
14. jrdb_history_fetch_config.json

これらがローカルに揃えば、Git投入用のディレクトリ構成へ実体を配置しZIP化できる。
