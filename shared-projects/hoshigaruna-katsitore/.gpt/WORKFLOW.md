# WORKFLOW — 欲しがるな、勝ち取れ

## 1. Start-up

作業開始時は次を読む。

1. `/.gpt/GITHUB_OPERATION_POLICY.md`
2. `/.gpt/README.md`
3. `/shared-projects/hoshigaruna-katsitore/README.md`
4. 本Projectの `.gpt/CONTEXT.md`
5. 本書

GitHub Connectorは `yukki0113/GPT` の接続のみを使用する。

## 2. Scope boundary

通常の新規実装・文書・schema・adapterは次のroot以下へ置く。

```text
shared-projects/hoshigaruna-katsitore/
```

既存の次の領域等は別Projectの正本である。

```text
horse-racing/
boat-racing/
local-horse-racing/
```

共有Project側の都合だけで直接改修しない。

既存機能が必要な場合は、まずread / auditして利用可能なinterfaceを確認し、必要なら本Project側に薄いbridge / adapterを設ける。既存実装そのものの改修が必要な場合は、けんしょー管理側で影響範囲を確認してから行う。

## 3. GitHub operation

Repository共通のA/B/C/Dルーティングに従う。

- Read / Audit: 直接read
- UTF-8 text change: 原則direct Git change
- pure deterministic処理: GPT実行環境を第一候補
- Actions-native要件がある場合のみIssue / Actions

通常の文書更新やadapter実装のためだけにIssueを作らない。

並列writeではforce禁止。stale / conflict時はlatest mainを再取得し、自分の差分だけ再構築する。

## 4. Member-first integration

メンバーの既存分析方法を技術都合だけで変更させない。

例:

```text
りょーたのExcel原本
  -> ryota adapter
  -> canonical / machine-readable output
  -> GPT統合
```

おーじのJRA-VAN回顧資産も、取り込み方法が決まるまでは既存運用を維持する。

けんしょーの既存データ基盤も、共有Projectへ複製正本を作ることを既定としない。

## 5. Integration output

統合時は最低限、次を区別する。

- けんしょー由来
- りょーた由来
- おーじ由来
- 3人の一致点
- 意見が割れている点
- GPTが新たに整理・推論した部分

GPTの整理結果を、メンバー本人の発言として書き換えない。

## 6. Data / asset routing

- GitHub: source / docs / schema / adapter / config / test
- Project Google Drive: 共有原本 / Excel / 大容量資産 / 分析成果物
- Project外部管理source: 明示的interface / delivered asset経由

詳細は `.gpt/DATA_BOUNDARY.md` を参照する。

### 6.1 まきば回顧馬台帳

まきばが個人チャットで挙げる回顧馬は、Project Google Drive上のGoogleスプレッドシート `回顧馬` を正本とする。

- Spreadsheet ID: `1h6hceLYBXFkUlfOiMMjMhStIs21GwDWyyzj0_Kdsuus`
- sheet: `回顧馬`
- columns: `日付,馬名,コメント`
- 過去回顧馬の検索、次走確認、競馬新聞等への紐付けではこのSheetを第一参照先とする。
- まきばの個人チャットで明確な回顧馬・回顧コメントが提示された場合、その発言を処理する同一ターンで正本へ反映する。
- ChatGPTは別チャットをバックグラウンド監視しないため、ここでの自動追記は「対象メッセージを処理する応答ターン中のDrive更新」を指す。

詳細な更新・重複排除・参照ルールは `docs/MAKIBA_REVIEW_HORSES.md` を正本とする。

## 7. Evolution

初期段階では共通prediction schemaを急いで固定しない。

実際の運用で各人の出力特性を観察し、繰り返し現れる要素が見えてから、
- schema
- adapter
- normalized output
- audit
を追加する。

「先にシステムを完成させてから使う」のではなく、「3人の実運用を邪魔しない範囲で必要箇所から整える」。
