# M5-C C0 — 知識スキーマ・ソース管理の受入監査（2026-11-11）

## 判定
**C0 PASS（公開コード・合成fixtureによる契約検証）**。C1以降の外部サイト実収集・実カード知識生成・展開ルート実ゲーム検証・private Drive知識保存は含めない。

## 実装
- `engine_m5/source_registry.py`: source ID一意、https URL、掲載/更新時点と確認時点の別管理、ゲーム形式MD/OCG/TCG/UNKNOWN、アクセス・収集範囲・許諾・コンテンツSHA、二次転載由来の参照整合・循環拒否。
- `engine_m5/knowledge_schema.py`: 設計された12エンティティ（source、theme_profile、claim、recipe、recipe_card、combo_route/node/edge、resource_state、package、assessment、refresh_queue）のschema v1 / primary ID / foreign key / 型 / 数量 / カードID形式 / 分岐参照 / 循環確認。UNKNOWNと未解決を保存可能。別証跡を持たない主張や展開をGAME_TESTEDに昇格しない。
- `engine_m5/tests/test_m5c_c0.py`: 架空のソース・カード名・構築データだけを使用。重複・欠損・URL・公開範囲・権利制限・循環・ID未解決・証跡なしGAME_TESTED・記事由来の不審な文言を**命令として実行しない**ことなど17件。
- 既存 `run_full_regression.py` の`engine_m5/tests/test_*.py`探索に自動包含。GitHub Actions全回帰 **296件 / skip 1 / failure 0**。M5スイート64件 PASS。プライベート実ZIP依存の既存1スキップはC0不合格ではない。

## 明確な限界
- 本検証器は**構造・参照・状態遷移の最低条件を検査する**ものであり、ソースの真偽、記事の転載関係の意味論、ゲーム裁定、個々のMD禁止制限、記事中に記述された悪意ある文章の完全自動識別は保証しない。記事内容をプログラム命令として実行する経路は持たない。
- 実際のMDカードマスター13,948枚や所持情報を取り込んでいない。C1の実データ投入時にカードIDの実在、現行本文SHA、収集許諾と媒体ごとの条件を再確認する。
- private本番SQLite、MD_CURRENT_HEAD、所持デッキcatalogは非変更。実個票は公開GitHubに含めない。
- C2の分岐遷移・ルール上の制約伝播の意味検証、C4の自動失効、C5のbundle公開/Drive保存は**C0で完了したとみなさない**。

## 次工程 C1
4テーマ（イビルツイン移行、海晶乙女・軍貫の低コスト候補、ブラック・マジシャンの負例）を初期教師ケースとして、各テーマ2ソース以上の候補を比較。1テーマ以上について記事時点のMAIN/EX構成をprivateに復元し、実DBに対するカードID照合・不足や規制不一致を記録する。ユーザーのスプライト型40/15は既存のprivate所持デッキ索引から**読取専用**で取得する。
