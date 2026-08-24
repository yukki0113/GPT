# JRDB PACI 自動取得

## 推奨構成

```text
Work実行環境/
├ fetch_jrdb_paci.py
├ jrdb_secret.py            ← 秘密情報。外部へ出さない
├ requirements_jrdb_paci.txt
├ .gitignore
└ downloads/
```

## 1. 認証ファイルを作成

`jrdb_secret.py.example` を参考に、
Work実行環境へ `jrdb_secret.py` を1回だけ作成します。

```python
JRDB_USER = "会員ID"
JRDB_PASSWORD = "パスワード"
```

`jrdb_secret.py` は次の用途では渡さないでください。

- ChatGPTへの再添付
- GitHub / Gitへの登録
- 改修依頼時の共有
- 成果物への同梱

今後改修するのは原則 `fetch_jrdb_paci.py` 本体だけです。

## 2. セットアップ

Python 3.10以上が必要です。追加パッケージは不要です。

```bash
python --version
```

## 3. 実行

```bash
python fetch_jrdb_paci.py --date 20260815 --show-url
```

既定保存先:

```text
downloads/PACI260815.zip
downloads/fetch_jrdb_paci_20260815.log
```

正常なZIPが既に存在する場合、再取得をスキップします。

## 4. URL規則

デフォルト:

```text
https://jrdb.com/member/datazip/Paci/YYYY/PACIYYMMDD.zip
```

HTTPを明示的に試す場合:

```bash
python fetch_jrdb_paci.py \
  --date 20260815 \
  --base-url "http://jrdb.com/member/datazip/Paci" \
  --show-url
```

HTTP Basic認証では資格情報が暗号化されないため、
実会員情報でのHTTP利用は推奨しません。

## 5. ログと秘密情報

ログには以下を出しません。

- JRDB_USER の値
- JRDB_PASSWORD の値
- Authorization ヘッダ

`.gitignore` では `jrdb_secret.py` を除外しています。

## 6. 今後の改修運用

改修時は `fetch_jrdb_paci.py` だけを共有してください。
`jrdb_secret.py` はWork実行環境側に固定しておき、
修正版の本体ファイルだけ差し替えて再実行する運用を想定しています。

環境変数が設定されている場合はそちらを優先し、未設定の場合にだけ
同じフォルダの `jrdb_secret.py` を読み込みます。
