# master_eval_media_collector

`@master_eval` のX/Twitter投稿に添付された画像を、投稿ID（status ID）単位で取得するためのコレクタです。

## 目的

Eval表の過去画像取得作業を定型化するために使用します。

このモジュール自体は「投稿から添付画像を取得する」ところまでを担当します。
取得画像のうち、

- Eval表本体
- 注意事項・説明画像

のどちらであるかの判定・選別は後工程で行います。

## 正本

GitHub `yukki0113/GPT` の `main` ブランチにある以下を正本とします。

- `horse-racing/eval/src/master_eval_media_collector.py`
- `horse-racing/eval/docs/README_master_eval_media_collector.md`
- `.github/workflows/eval_media_chat.yml`
- `.github/workflows/eval_media_manual.yml`

取得画像、metadata、validation report、実行ログ、最終ZIP等の日次成果物はGitへcommitしません。

## 動作環境

- Python 3
- 外部Pythonパッケージ不要
- Python標準ライブラリのみで動作

## 取得経路

公開されている以下の経路を順に試します。

1. FxTwitter public API
2. Twitter/X syndication endpoint

X公式画面のHTMLを直接スクレイピングする方式ではありません。

公開API・埋め込み経路は将来仕様変更される可能性があります。

## 基本実行形式

```bash
python master_eval_media_collector.py <投稿ID> [<投稿ID> ...] --out <出力ディレクトリ>
```

### 例

2026/07/18・07/19 の投稿IDを指定する例です。

```bash
python master_eval_media_collector.py \
  2078087318754259013 \
  2078437850614571317 \
  --out eval_20260718_19
```

## 出力

投稿IDごとにサブディレクトリを作成します。

```text
eval_20260718_19/
  2078087318754259013/
    metadata.json
    media_01.jpg
    media_02.jpg
    ...
  2078437850614571317/
    metadata.json
    media_01.jpg
    media_02.jpg
    ...
```

### metadata.json

取得に使用した経路と、取得元APIのレスポンスを保存します。

### media_XX.*

投稿に添付されていた画像です。
可能な場合は元サイズ (`name=orig`) を取得します。

## 終了コード

- `0`: 全取得成功
- `1`: メタデータ取得失敗、画像URL未検出、画像取得失敗のいずれかが発生

## Chat標準経路: GitHub Issue → Actions

日常のChat運用では `.github/workflows/eval_media_chat.yml` を使用します。Chat実行環境からFxTwitter、X syndication、`pbs.twimg.com` へ直接通信する必要はありません。

### 役割分担

1. Chatがユーザー指定日から `@master_eval` の対象投稿を探索する
2. Chatが対象日と投稿IDの対応を確定する
3. Chatが専用GitHub Issueを作成する
4. ActionsがGit正本のcollectorを実行する
5. Actionsが取得結果をartifact化してIssueへ結果コメントを返す
6. Chatがartifactを回収し、画像内容を見てEval表本体だけを選別する
7. Chatが最終ZIPを作る

投稿ID探索は現時点でもcollectorの担当外です。投稿URLまたは投稿IDがユーザーから与えられている場合は探索を省略できます。

### Issue形式

タイトル:

```text
[EVAL_MEDIA_REQUEST] <request_id>
```

本文は生のJSONとします。推奨形式は `targets` です。

```json
{
  "targets": [
    {
      "date": "2026-07-18",
      "post_id": "2078087318754259013"
    },
    {
      "date": "2026-07-19",
      "post_id": "2078437850614571317"
    }
  ]
}
```

簡易形式として同数の `dates` と `post_ids` も使用できます。

```json
{
  "dates": ["2026-07-18", "2026-07-19"],
  "post_ids": ["2078087318754259013", "2078437850614571317"]
}
```

任意で `output_label` を指定できます。`output_label` は英数字、`.`、`_`、`-` のみ使用できます。任意パスは受け付けず、Actions側で安全な作業ディレクトリを生成します。

`request_id` はChat側で毎回一意に生成します。

### Actions処理内容

1. Issue作成イベントでActions起動
2. `main` をcheckout
3. Issue本文JSONを検証
4. Git正本の `master_eval_media_collector.py` を実行
5. 各投稿IDについて `metadata.json` と1枚以上の `media_XX.*` が存在するか検証
6. `resolved_request.json`、`validation_report.json`、`run_status.txt` を生成
7. 投稿ID別取得物と検証物をartifact化
8. 同じIssueへ `EVAL_MEDIA_RESULT` コメントを投稿
9. Issueを自動クローズ

結果コメントには少なくとも以下が含まれます。

- `request_id`
- `run_id`
- `artifact_name`
- `fetch_exit_code`
- `validation_exit_code`
- 対象日と投稿ID
- validation結果
- Chat側の後工程

Chatは `fetch_exit_code=0`、`validation_exit_code=0`、`validation.validation_status=success` を取得工程の成功条件とします。

artifact保持期間は14日です。取得画像や実行成果物はGitへcommitしません。

### validationの範囲

Actionsのvalidationは、対象投稿ごとに

- `metadata.json` が存在する
- `media_XX.*` が1枚以上存在する

ことを確認します。

**Eval表本体か注意事項画像かの内容分類は行いません。**

画像順は固定仕様ではありません。過去実績で `media_01` がEval表、`media_02` が注意事項であることが多くても、自動採用してはいけません。

## Eval表運用での後工程

1. artifactを回収
2. 各画像を確認
3. Eval表（馬名・馬番・複勝圏内率が表形式で並ぶ画像）だけを選別
4. 注意事項・説明・告知画像を除外
5. 日付が分かるファイル名に整理
6. ZIP化

通常は土日の2開催日をまとめて指定します。

例:

```text
2026/07/18〜07/19 のEval表画像取得をお願いします。
```

最終成果物の命名規則:

```text
eval_YYYYMMDD_YYYYMMDD_Eval表画像.zip
```

通常の土日2日分では、最終ZIPにEval表画像が2枚あることを確認します。

## 予備経路

### 人間向け workflow_dispatch

`.github/workflows/eval_media_manual.yml` を使用します。

入力:

- `dates`: `YYYY-MM-DD` を空白またはカンマ区切り
- `post_ids`: `dates` と同じ順序・同じ件数の投稿ID
- `output_label`: 任意

この経路もGit正本のcollectorを使用し、取得物・`resolved_request.json`・`validation_report.json`・`run_status.txt` をartifact化します。

### 直接Python実行

Chat/ローカル実行環境からの直接Python実行は、デバッグ・緊急時の補助経路です。外部通信制約に左右されるため、日常運用の第一選択にはしません。

## 注意事項

- 投稿IDの探索自体はこのPythonの担当外です。
- X側または公開API側の仕様変更により取得不能になる可能性があります。
- 画像内容のEval表判定は自動化されていません。
- 日付と投稿IDの対応はIssue本文と `resolved_request.json` に残ります。
- Actions Workflowを変更した場合は、このREADMEも同時に更新します。
