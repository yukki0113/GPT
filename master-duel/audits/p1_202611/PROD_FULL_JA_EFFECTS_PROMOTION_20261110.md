# 本番DB世代1 — 2026-11-10

## 結果
非公開Google Driveの本番HEADを世代0から1へ更新し、独立読み戻しを確認した。旧HEADと旧SQLite ZIPは保持。

- スナップショット：`md-prod-001-full-ja-effects-20261110`
- 分類：`PRIVATE_PERSONAL_DECK_DB_WITH_JA_EFFECTS`
- カード13,948件、属性13,948件、MDレア13,948件、日本語効果テキスト13,948件
- 効果文欠損0、カードID未解決0、所持・所持履歴0
- ZIP SHA-256：`9239a9d8a7888490975e3a01688ed8ee64d8d5d23d2bf0cfd9ef4796be6d2762`
- SQLite SHA-256：`0f498b5c56b8e119232e9e3212038ee1e8c20d0e09664d6791415975ae0f725e`
- HEAD SHA-256：`db879115e92c09891df286b06aa9ecffeef9468c26e71e248d14b38d2b33ea87`
- SQLite integrity=ok、foreign key violations=0
- P1/P2/P3と効果文投入の回帰93件PASS、skip 0
- 正式P3 previewの本番スコープ読取PASS（既知名・同名別カード・存在しないカード）。
- 現在の効果本文は `UNVERIFIED_SOURCE`。ゲーム内公式全件照合済みではない。
- 個人用・非公開限定。公開配布や外部提供を行わない。
- `MD_CURRENT_HEAD.json` が本番唯一の正本参照。Driveのatomic CASは未提供、単一ライターのみ更新。
- 旧HEADバックアップ `MD_CURRENT_HEAD_BACKUP_gen0_20261110.json`、元の空DB ZIPは保存継続。
- ZIP実データ・日本語効果本文・個人の所持履歴を公開GitHubには置かない。

今後の重点：汎用カード・出張パーツ所持登録対象、効果に基づく検索とデッキ支援、禁止制限の時点検証。
