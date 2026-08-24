# master_eval_media_collector

`@master_eval` のX/Twitter投稿に添付された画像を、投稿ID（status ID）単位で取得するためのコレクタです。

## 目的

Eval表の過去画像取得作業を定型化するために使用します。

このモジュール自体は「投稿から添付画像を取得する」ところまでを担当します。
取得画像のうち、

- Eval表本体
- 注意事項・説明画像

のどちらであるかの判定・選別は後工程で行います。

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

## Eval表運用での後工程

1. 各画像を確認
2. Eval表（馬名・馬番・複勝圏内率が表形式で並ぶ画像）だけを選別
3. 注意事項・説明画像を除外
4. 日付別に整理
5. 必要に応じてZIP化

Work運用では、通常は土日の2開催日をまとめて指定して使用します。

例:

```text
2026/07/18〜07/19 のEval表画像取得をお願いします。
```

最終成果物の命名例:

```text
eval_YYYYMMDD_YYYYMMDD_Eval表画像.zip
```

## 注意事項

- 投稿IDの探索自体はこのPythonの担当外です。
- X側または公開API側の仕様変更により取得不能になる可能性があります。
- 画像内容のEval表判定は自動化されていません。
