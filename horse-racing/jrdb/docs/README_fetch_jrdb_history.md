# JRDB History Fetcher v0.1

JRDBの年次ZIPと2026年以降の単日ZIPを取得するPythonです。標準ライブラリのみで動作します。

## 実測済みURL規則

- 年次BAC: `https://jrdb.com/member/datazip/Bac/BAC_2025.zip`
- 単日UKC: `https://jrdb.com/member/datazip/Ukc/2026/UKC260823.zip`

初期設定では同じ規則を `BAC / KYI / SED / SKB / CYB / CHA / UKC / KKA` に展開しています。系統別ディレクトリ名はconfigで変更できます。

## 認証

環境変数 `JRDB_USER` / `JRDB_PASSWORD` を優先します。なければスクリプトと同じ場所の `jrdb_secret.py` を参照します。

```python
JRDB_USER = "..."
JRDB_PASSWORD = "..."
```

認証情報はログ・manifestへ出しません。

## URL確認

```bash
python fetch_jrdb_history.py --year 2025 --kinds BAC --dry-run
python fetch_jrdb_history.py --date 20260823 --kinds UKC --dry-run
```

## 初回バックフィル

2024・2025はGoogle Driveへ手動保存済みのため、初回自動取得は2010〜2023を想定します。

```bash
python fetch_jrdb_history.py \
  --from-year 2010 --to-year 2023 \
  --output-dir ./00_raw_local \
  --sleep-seconds 2 \
  --continue-on-error
```

## 単日取得

```bash
python fetch_jrdb_history.py --date 20260823 --output-dir ./00_raw_local
```

日付範囲も指定できます。非開催日は404として記録し、異常終了扱いにはしません。

## キャッシュ・整合性

既存ZIPが以下を満たせば再取得しません。

1. ZIPとして開ける
2. `testzip()`で破損なし
3. 対象系統prefixのファイルが1件以上ある

ダウンロードは `.part` に保存し、検証成功後のみ正式名へ置換します。取得結果はJSONL manifestにURL、サイズ、SHA-256、ZIP内件数、statusを記録します。

## Google Drive連携

Python自身にはGoogle OAuthを持たせません。取得・検証後、ChatGPT Workの接続済みGoogle Drive機能で

`/GPT/JRDB/00_raw/<TYPE>/`

へアップロードする想定です。

`jrdb_history_fetch_config.json` には現在の8フォルダIDを `drive_handoff.folder_ids` として保存しています。これによりJRDB認証とGoogle認証をPython内で二重管理しません。
