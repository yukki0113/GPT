# M3 初期実装監査 — 日付付きMD規制とレア別CP（2026-11-10）

## 前提と実ソース監査

- 非公開Drive source/current.vector.json は 2026-11-05 候補215件。元ファイルSHA256 2651601cb3bf9b66dde522eff92207968c9b9f63f4b82632910ccacdf5210781。
- 非公開本番MDカードマスター13,948件と結合し、candidate ID存在 215/215、欠損0。データ取得と検証は読取専用。
- 元vectorは日付・215件のIDと値だけで、出典・FORMAT・ゲーム内確認の保証がない。新しい2026-11-05の適用予告自体は公式SNSで確認可能だが、215値の全件を公式確認済みとして保存しない。
- 原本のDB本番HEADは世代1、inventory/history 0件で変更していない。規制テーブルへの本番書き込みは実施しない。

## 実装と受入対象

regulation_m3/snapshots.py: strict versioned schema、日付・時点・MDフォーマット・規制 0/1/2/3・SHAと出典の検証。legacy vectorはCANDIDATE_ONLYへ変換し、未掲載をUNKNOWN、新しい未検証を過去のGAME_VERIFIEDで代用しない。同日複数スナップショットは曖昧扱い。

regulation_m3/evaluation.py: 保守的な既存デッキレシピ判定に検証済みの禁止制限だけを与え、所持数と採用可能枚数を結合。CP-N/R/SR/URを独立した通貨として見積もり、CP予算は通貨ごとに比較。候補CPルールやUNKNOWN所持なら確定のPASS/FAILを返さない。

regulation_m3/tests/test_m3.py: 検証済みと候補の切り分け、施行日・重複・日付逆転・未掲載UNKNOWN、0/1/2/3、所有 min、規制違反、候補CP、SR予算とN予算の非互換等の架空テストを追加。

## 未達・安全ルール

- 現行MDゲーム画面の規制全件検証は未完了。215件の候補値を実際の制限枚数として確定できない。
- 生成CP単価は候補と確認済みを分離し、未確定値での予算PASSを保証しない。カードごとの生成可否も未検証のものはUNKNOWN。
- 本番DBへのbanlist導入、非公開HEAD切替、ユーザー所持の登録は未実施。ユーザーに追加所持申告を求めずM3の基盤だけ先行する。
- レシピは入力されたもののみ評価。低レアテーマ自動発掘はM6。

## GitHub/CIの検証

初回実装後に、main反映コミットとGitHub Actionsの回帰件数・skip・成否を追記する。
