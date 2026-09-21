# まきば回顧馬台帳 運用契約

## Purpose

「まきば」が個人チャットで挙げる回顧馬を、後から検索・再利用できる共有資産として蓄積する。

この台帳は、過去の回顧馬検索、次走注目馬の確認、将来作成する競馬新聞等への紐付けに利用する。

## Canonical source

正本はProject Google Drive上の次のCSVとする。

- file: `回顧馬.csv`
- Drive file ID: `1PLKLRwmwG5lIuzdfk6ABbCahwzNQEjBo`
- URL: `https://drive.google.com/file/d/1PLKLRwmwG5lIuzdfk6ABbCahwzNQEjBo/view`

GitHubへCSV内容の複製正本は作らない。
本書は保存先・書式・更新条件・参照ルールの運用契約を正本とする。

## CSV contract

ヘッダは次の3列で固定する。

```csv
日付,馬名,コメント
```

1つの回顧内容を1行として扱う。

- 日付: まきばが明示した日付をそのまま記録する。
- 馬名: 対象馬名。
- コメント: まきば本人の回顧内容。意味を変える要約やGPT独自評価を混ぜない。
- 日付が示されていない回顧は、日付を推測せず空欄にする。
- ASCII comma、double quote、改行を含む値は通常のCSV escapingを行う。

## Automatic capture in Makiba chat

まきばの個人チャットで、まきば本人が馬名と回顧内容を明確に提示した場合、そのメッセージを処理する同一ターンで正本CSVへ反映する。

例:

```text
ナックスプレンダー
2/1 出遅れ、4角ぶん回してよく3着きた
2/21 すごい脚で追い込んでる
```

この場合は日付ごとに別行で追加する。

明示的な「保存して」という依頼を必須条件にしない。
ただし、一般的な雑談・仮説・質問まで回顧メモとして誤登録しない。

ChatGPTは別チャットをバックグラウンド監視できないため、「自動追記」とは、まきばの個人チャットで対象発言を処理した応答ターン中にDrive更新を実行することを意味する。

## Write rules

追記時は次を守る。

1. まず現在のCSVを読み、既存内容を保持する。
2. `日付 + 馬名 + コメント` が完全一致する既存行は二重登録しない。
3. 新規回顧は原則appendする。
4. 明示的な訂正依頼があった場合のみ、対象行の修正として扱う。
5. GPT独自の推測日付、評価、補足コメントを台帳へ追加しない。
6. Drive更新に失敗した場合は保存済みと扱わず、そのチャット内で失敗を明示する。

## Native Drive write transport

通常CSVはGoogle Sheets APIで直接セル追記できないため、Project Google Drive上のnative Google Sheetを**書き込みバッファ**として利用する。

- buffer file: `_system_回顧馬_csv_buffer`
- buffer Spreadsheet ID: `1h6hceLYBXFkUlfOiMMjMhStIs21GwDWyyzj0_Kdsuus`
- bufferは正本ではない。検索・新聞連携では参照しない。

更新手順:

1. 正本 `回顧馬.csv` を毎回読み直す。
2. CSVをparseし、今回追加する行をmergeして重複排除する。
3. buffer SheetのA:Cを現在のmerge結果で置き換える。
4. buffer Sheetを `text/csv` でexportする。
5. exportで得たruntime file referenceを使い、Drive `files.update` 相当で正本file ID `1PLKLRwmwG5lIuzdfk6ABbCahwzNQEjBo` のbytesを置き換える。
6. 更新後に正本CSVを再読込し、header・既存行・追加行がすべて存在することを確認する。
7. 検証失敗時は保存成功と扱わない。

同時更新対策として、書き込み直前にも正本を再読込する。
最初のread以降に正本が変化していた場合は、最新内容に今回の行だけを再mergeしてから更新する。
更新後の再検証で欠落を検出した場合も、最新正本から再mergeする。

このtransportはProject標準のnative Google Drive connectorだけで完結し、GitHub Actions / Service Account bridgeは使用しない。

## Read / lookup rules

まきばが「前に言った馬」「過去の回顧馬」「○○のメモ」等を検索する場合、このCSVを第一参照先とする。

- 馬名をキーに該当行を取得する。
- 複数日付のメモがある場合は全件保持する。
- チャット履歴は補助情報として利用できるが、保存済み回顧についてはCSVを正本とする。
- CSVにないことだけを理由に「まきばが評価していない」と断定しない。

## Newspaper / integration rules

競馬新聞や統合予想等で出走馬と回顧情報を紐付ける場合、馬名をキーにこのCSVを参照する。

該当回顧を利用した場合は、内容が「まきば由来」であることを保持する。
GPTによる整理・要約を行う場合も、本人発言とGPT整理を混同しない。

## Source integrity

このCSVはProjectの共有原本として扱う。
共有権限、誤更新、重複、文字化け等に異常が見つかった場合は、正本の整合性問題として管理室で扱う。
