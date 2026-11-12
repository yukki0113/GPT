# M6-6 実データ統合監査（2026-11-12）

## 結論

**M6-6：最新非公開Generation5正本に対する構造的な実コード統合試験はPASS。ゲーム内の合法性・展開ルート・デッキの実戦強度はREVIEW_REQUIREDであり、完成推奨は不可。**

合成入力ではなく、Driveの現行HEAD・snapshot ZIP・SQLite・CP方針・M5-C sidecarの原本バイトを使用し、**実際の公開`engine_m6` Pythonコード**でM6-1→M6-2→M6-3→M6-5A検索→M6-5B素材スクリーン→M6-5C再構成→M6-4評価→M6-5A探索監査→M6-5比較→M6-5 archive作成/検証を接続した。

ただしM6-5Bの「効果発動・複数素材の同時展開・出張ロックのゲーム上の成立」は検証できていない。本試験では、カード本文のSHAつき読み取りと**仮説の素材集合**に対する文字列条件の確認までである。出張索引M5-Aは古いGeneration3由来のため、実データ新構築で出張を無検証採用しない。テーマCOREが公式に必須と確定したわけではない。

## 1. 現行sourceの完全性

- 現行private HEAD Generation5、原本SHA256 `0799c1d946bf31f10fd92187e933ebaa17caa4aea16994a60c72d55f7e4949d9`。
- スナップショット ZIP SHA256 `f8bc126ebf9335e8aa3cd9ffaaeceb2afd7bb8d944d13bfd5d5ba389b0b0f573`。
- SQLite raw SHA256 `662f905fe9fe3f6b41d26c33e8780bd920743e6348903cd0d53bcb99ce77a289`。
- M5-C sidecar ZIP SHA256 `f3a5c4798fb3ce8b4c78e9c9ea2a704ad34dfb5fb5eb70aea1c5c76c10d09e53`。マニフェスト個別SHA検査、DB Generation5ピン整合。
- CP policy raw SHA256 `47fb498b55df2e6b95d46a04e14f7a2ce1946a9ebad91a7b8ca9a062900614f9`。
- **HEADをスナップショット取得の前後でDriveからそれぞれ取得し、バイト・SHAが一致することを確認**。SQLiteは読み取り専用、`integrity_check=ok`、所持台帳は135種類全件。登録済みデッキ・HEAD・ユーザー所持原本の書き込みはゼロ。
- `preflight_status=PARTIAL`はカード効果/禁止制限/登録済み所持全行の実戦上の評価がまだ検証途中であることを含む。「原本SHA不一致」を意味しない。

## 2. 5テーマの実モジュール実行（虚偽のレシピ自動補完禁止）

| Profile | M6-2 pool候補 | M6-3構造レシピ | M6-6 |
|---|---:|---:|---|
| 軍貫（SUSHIP） | 34 | 2 | 新しいSTRUCTURAL構築1案、REVIEW_REQUIRED |
| イビルツイン（EVIL_TWIN） | 34 | 0 | source記事のMAIN39枚、完成不可、INSUFFICIENT_EVIDENCE |
| 海晶乙女（MARINCESS） | 0 | 0 | 完成sourceレシピ不足、INSUFFICIENT_EVIDENCE |
| ブラック・マジシャン（DARK_MAGICIAN） | 0 | 0 | 完成sourceレシピ不足、INSUFFICIENT_EVIDENCE |
| スピードロイド（SPEEDROID） | 0 | 0 | 展開ルートsourceはあるが完成レシピ不足、INSUFFICIENT_EVIDENCE |

不足する4テーマを架空の40枚で埋めず、アーカイブも勝手に作成しないことを**実データで確認**した。

## 3. 軍貫：教師由来EX7から新EX14構造候補へ

- M6-3教師構造はMAIN40/EX15とM5-C低コストvariant MAIN40/EX7。低コストvariantは教師からURを外した時点でEX残8枠、元案は「代替探索が不十分」というユーザー指摘があった。
- M6-5A `discovery.search_cards`で原本からテーマ候補8種類、所持汎用MAIN候補9種類、テーマ外汎用EXを含む候補13種類を、独立したSHAピン検索で再取得した。これらは**AIによる仮の役割注釈を付けた候補**で、全ての組合せの正しさを保証しない。
- M6-5B `load_effect_anchors`＋`screen_extra_materials`でランク4の「レベル4モンスター×2」、リンク素材の「カード名が異なるモンスター2体」等を照合。レベル5×2の別Xは根拠不足として保留。仮の「レベル4を2体供給できる盤面」には明確に`HYPOTHESIS`を設定し、同時素材供給がゲーム内で確定していると扱わない。
- M6-5C `recompose_portfolio`が**MAIN40 / EX14 / 新規UR生成上限0**の構造案を実際に作成した。所持済み汎用を所持枚数以内で採用し、教師にない汎用Xと汎用LINK候補を取り込んだ。EXは未使用枠1、役割/効果の再検討が必要。**EX14が最適解と判明したわけではない**。
- M6-4 `evaluate_structural_candidate`の実データ評価は`NEW_UR_CRAFT_ZERO=PASS`相当だが、要求された`LOW_RARITY_CORE`の必須テーマCOREが未確定で、`requested_mode_gate=INDETERMINATE`。現行MD禁止制限・手持ちCP残高・実戦ルート/強度は未検証。
- M6-5A `audit_reconstruction`は`REVIEW_REQUIRED`。出張の完全ルート、別テーマ混合の相性、教師の失われた機能の検証などで未解決理由を残した。M6-5B `audit_effect_routes`はこの実行では空の効果主張/ルートを受け、非認証の`REVIEW_REQUIRED`を返した。これを効果や展開の成立確認と誤認しない。
- M6-5 `compare_candidates`、`make_proposal_archive`、`verify_proposal_archive`を**実モジュール**で実行してprivate候補を不変ZIPに保存。使用原本のSHA・アーカイブ/manifest SHA一致、Driveへprivate新規保存後のraw読み戻しも確認。

## 4. 実データで発見・修正した不整合

1. **M6-4 CP方針の余分な正規メタデータ**：現行の原本CP方針には`policy_id` / `checked_at` / `source`が存在するが、`evaluate.py`は最初の3フィールド以外を一律拒否していた。任意の既知3フィールドだけを許し、未知フィールドの拒否・raw SHA必須は維持するよう修正。
2. **LINK値がNULLの汎用EXが検索から漏れる**：現行DBはLINKモンスターの`card_attributes.link`がNULLのことがあり、所有済みのリンクEXがM6-5AのEX検索で発見されない。カード本文の「このカードがＬ召喚」の記載と明示カードIDを併用する限定検出を追加し、MAINへの誤分類も避ける。LINK数値を勝手に2へ推定しない。**この本文パターンに該当しないLINK/融合/シンクロは依然網羅されない**。
3. **M6-5B仮説素材の過剰な証拠ラベル**：構築前の「レベル4を2体供給できる」という盤面仮説は`SOURCE_OBSERVED`扱いにせず、`HYPOTHESIS`を明示して素材の文字列スクリーニングのみ許容する。ゲームテスト完了ではない。

## 5. 公開の合成回帰テスト

- 新しい`engine_m6/integration.py`により、全段階を同一SHA/同一HEADで接続する実行経路を固定化した。
- `engine_m6/tests/test_m6_6.py`に**11件**の合成回帰を追加：CP方針の実データ形式、未知フィールド拒否、SHA改竄、LINK値NULLのEX・MAIN分類、カードID完全一致の安全な絞り込み、仮説素材の非認証、HEAD不一致時停止。
- 全公開テストは架空カードと偽のヘッダを使用。実所持の個票や作成デッキはGitHubに置かない。
- GitHub Actions（最新ブランチ版）で**M6 220件PASS、プロジェクト全593件PASS・既存スキップ1件・FAIL0**。
- 実データの追加受入はprivateの実Python modulesを動かした結果であり、合成回帰だけの独立試算とは区別した。

## 6. private成果物（Driveのみ）

| private成果物 | bytes | SHA256 |
|---|---:|---|
| `MD_M6_6_PRIVATE_INTEGRATION_AUDIT_20261112.json` | 4558 | `64c9d7ae87a364a9a25236b1958857e38d1c154fb260a7c4bd13c511e0fe78f0` |
| `MD_M6_6_PRIVATE_INTEGRATED_PROPOSAL_20261112.zip` | 2698 | `4d25f330fba06ed6dc7a92b41cd4a94491128e5bf5ae41882f17c61614d5082a` |
| `MD_M6_6_PRIVATE_INTEGRATED_PROPOSAL_20261112.manifest.json` | 497 | `5de656ec90038adeed72f3fd3c625c4cdccf09cdb96028be25d855e150802ab7` |
| `MD_M6_6_PRIVATE_AUDIT_MANIFEST_20261112.json` | 841 | `f8d819cfa99c427c7b64d030561f3f3fe93dd64159acccea35055a7201aa482f` |
| `MD_M6_6_PRIVATE_REPLAY_INPUT_20261112.json` | 14340 | `0876605b8e8132111e97d6753cf06952f4c104b46b1deb2fd86d07a24a10b888` |

これらはprivate Drive `GPT/MasterDuel/DB`へ保存し、元ファイルとraw読み戻しのSHA/bytes一致を確認。再現入力には仮の役割・優先度・素材仮説を残し、暗黙にレビュー済みの事実へ昇格させない。

## 7. 次のM6-7受入に必要な実質課題

構造的な接続は通ったが、本来のユーザー目的は「所持資産だけで実戦に耐えるデッキ」の提案であり、**追加のカード効果・展開・召喚ロック・現行禁止制限の確認がなければ、ユーザー受入をPASSにしない**。次のM6-7では軍貫MAIN40/EX14の候補をカード1枚ずつ検討し、教師URを外した後の主要勝ち筋と所持汎用6枚のバランス、少なくとも複数展開の必要素材・リスクをチェックする。EXの未使用1枠は空のままでよいと断定せず、その代替候補と採否理由を示す。さらに「SR以下のみ」「所有URは可」「所持生成CP制限」「EX依存のMAINパーツ」などの依頼を構築スレッドで受け入れる。
