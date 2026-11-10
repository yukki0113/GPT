# M3 CPユーザー確認済みルール導入（2026-11-10）

## 確定したこと

- ユーザーは2026-11-10の会話で「レアリティごとにカード1枚30CP」を明示的に正しいと確認した。**NはCP-N、RはCP-R、SRはCP-SR、URはCP-UR**を各30消費し、レア間では代用不可。
- 別ソース参照: [AppMedia カード生成](https://appmedia.jp/master_duel/27458091)、[Yugipedia Craft Points](https://ftp.yugipedia.com/wiki/Craft_Points) も同一説明。ユーザー確認と公開資料の一致によって **CP単価のみ USER_CONFIRMED** とする。これは各カード生成可否や禁止制限の GAME_VERIFIED を意味しない。
- 私的Drive `GPT/MasterDuel/DB/MD_CP_POLICY_USER_CONFIRMED_20261110.json` に独立スナップショットを保存。SHA256 `47fb498b55df2e6b95d46a04e14f7a2ce1946a9ebad91a7b8ca9a062900614f9`。内容は `policy_id`, `effective_on=2026-11-10`, `checked_at`, `source`, `verification=USER_CONFIRMED`, `cp_per_card={N:30,R:30,SR:30,UR:30}`。Drive別操作で再取得してSHA一致確認済み。
- `effective_on=2026-11-10` はこのルールを**確認した時点**を表す。カード生成システムがこの日に変更されたという主張ではない。
- このCPポリシーは**SQLiteの世代を増やさない独立・版付きの私的参照JSON**。本番HEAD世代3・禁止制限候補215件（UNVERIFIED_SOURCE）・所持台帳は一切更新しない。

## 実DB監査と境界

- 実世代3ZIPのSQLite SHAとHEAD SHA一致、integrity_check=ok、foreign_key_check 0。13,948カード・効果、所持5件、規制候補215件。現行MDカタログの `craftable` 内訳は `UNKNOWN=13,931`、`NO=17`、`YES=0`。**一般的な生成コストが確定しても、未知の生成可否が自動的にYESになるわけではない**。
- `USER_CONFIRMED` は`GAME_VERIFIED`とは別状態で保持。規制 `UNVERIFIED_SOURCE` の候補数値でレシピ合法性を確定させない。禁止カードの中には生成できるものもあるため、禁止制限と生成可否は別フィールド。
- CP予算はレアリティごとの残高だけを使い、未指定の通貨は無制限とせず `CP_BALANCE_UNKNOWN:<R>` として判定保留。所有UNKNOWN、生成可否UNKNOWN・NOが必要枚数に絡む場合、CP支出の確定可否とデッキ合法性を分ける。
- CP現在残高やユーザーの追加所持枚数は未申告なので推定しない。

## コードと検証

- `regulation_m3/evaluation.py`: `USER_CONFIRMED` 出典つき単価を受入、`price_rule_confirmed` と `estimate_is_confirmed` を区別、生成可否不明なら予算の確定PASSを出さない。
- `regulation_m3/cp_policy.py`: プライベートJSONのバイトSHA固定読込、適用日選択、未来ポリシー禁止、同日重複拒否、未検証新版による旧版への黙示fallback禁止。
- `regulation_m3/bridge.py`: Drive HEADと参照ZIP SHA/SQLite schema・SHAの確認→隔離展開→SQLite版付き規制読込→CP JSON版選択→与えられたレシピの評価。外部Driveへの書込ゼロ。
- `regulation_m3/tests/`: 生成CPの架空fixtureで、所有・生成可否・レアリティ別予算、候補規制との独立性、将来日付、SHA改ざん、HEAD/ZIP不一致を回帰検証。実カード本文や私的所持個票は公開CIに渡さない。
- GitHub Actions のCI結果・mainコミット・追加実DB読取スモークは実施後にこの監査へ追記する。

## M3残課題

- 2026-11-05付規制候補215件のゲーム内/公式全件照合と、少なくともテーマ推薦に使うカードの生成可否を出典付きで確定する。
- 未登録所持枚数、CP-N/R/SR/UR残高はUNKNOWNのまま。M4/M5/M6へのデッキ評価APIはこの未確定状態を伝播させる。
