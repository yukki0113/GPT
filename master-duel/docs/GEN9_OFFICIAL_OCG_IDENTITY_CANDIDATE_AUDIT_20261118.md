# Gen9 公式OCGカードID照合と所属候補の段階取り込み（2026-11-18）

## 目的と実施結果

前工程の出典バイトSHA付き台帳を実際の情報収集に接続する前段階として、公式カードDB「遊戯王ニューロン」の**カード詳細ページ**を参照し、private Gen9に記録されたカードID `konami:<cid>` と公式URLの `cid`、公式ページのカード名を照合した。

- 実施した**限定的な手動ブラウザ照合は3件**：Gen9のCID・名称と、公式サイトのカード詳細CID・主見出しの名称が整合。
- 取得元：`https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=<cid>&ope=2&request_locale=ja`。公式ページの「関連カード」欄に掲載された名称を主カードの本人確認へ使わず、詳細上部の主見出しだけを照合対象とした。
- Web検索・ページ表示経由の照合であり、**HTTP応答の原本バイトを取得できていない**。よって3件とも出典原本SHA不明、カードID照合候補 `NOT_REVIEWED`、テーマ所属 `UNVERIFIED`、MD収録 `UNVERIFIED`。公式所属根拠を持つ `REVIEWED` レコードは**0件**。
- 3件分のカード名、カードID、個別ページURLを含む照合候補データは非公開ローカルJSONにのみ記録し、公開GitHubに置かない。これは所持カードの確認・所属確定・構築候補の選抜ではない。

## 新規実装

`engine_m6/official_identity_candidates.py`：将来の原本バイト収集用の **card identity candidate** ステージング。

- 外部ネットワークから任意のURLを自動収集しない。呼び出し側が明示した原本 `source_bytes` を受け取り、そのバイト列のSHAを生成。
- HTTPS・ホスト完全一致 `www.db.yugioh-card.com`・詳細アクションパス・クエリ `cid, ope=2, request_locale=ja` に限定。リダイレクト先・類似ドメイン・複数CIDを正規URLと誤認しない。
- カード詳細の `h1` に期待するGen9カード名を要求し、関連カード一覧など本文の出現だけで本人確認しない。
- 応答のUTF-8原本、UTC取得時点、元URL、CIDと名称を照合する。
- **出力は `SOURCE_HEADER_ALIGNED_CANDIDATE` と未レビュー状態のみ**。カード名にテーマ文字列が含まれていても `archetype_membership=UNVERIFIED`、`master_duel_coverage=UNVERIFIED`、`material_eligibility=UNVERIFIED` のまま。
- 元サイトにアクセスできたこと、HTMLに記述があること、SHAが計算できたことは、カード所属が公式に確定したことを意味しない。未検証のHTMLバイトを外部から供給できるため、発信元の真正性・取得ログ・コンテンツ完全性の証明は別途必要。

`engine_m6/tests/test_official_identity_candidates.py`：架空HTMLのみの回帰テストを追加。CID違い・偽装ドメイン・HTTP・重複クエリ・UTF-8不正・取得時点未指定・本文だけに名前があるケースを拒否し、出力が未レビューのままであることを確認。

## private Gen9整合性と本番昇格禁止

- HEAD SHA256: `e592b34198c290f59580976b6b861de893e6708596eb9df57b3b6e594643a66a`。
- ZIP SHA256: `0fa5fc724f8ab7671404f9297fb240095127840725d1bfd45a7431357467432f`。
- SQLite SHA256: `dd1e7d85c55b4ba764110af24d852d886abb787e72e18be2c5fd59ef57243411`。
- SQLite `integrity_check=ok`、外部キー違反0件、現行schema v4。private正本への書き込みはしていない。
- 前工程の厳密単独ヘッダー103件（XYZテーマ26、LINKテーマ68、LINK非トークン9）は変更なし。**今回新たに確認したのはカードID同一性候補3件であり、テーマ所属確認件数は0件**。
- 公式OCGカード詳細の存在からMaster Duelへの収録、当時のテーマ所属、素材適格性、召喚の合法性を推定しない。M6-5B `REQUIRES_REVIEW` を維持。

## 次の検証ゲート

1. 公式ページ原本の取得手段を整備し、実バイトSHA・取得時刻・応答最終URL・HTTPメタデータを記録。検証可能な入力に限定して今回のcandidateステージングを再実行。
2. テーマ所属を肯定する場合、公式ルール・カードテキスト・テーマ条件の適用範囲を**カードIDごとに個別審査**し、単なる表記上の部分一致と区別する。必要なら名称変更効果・ゲーム中の扱いを別に記録。
3. 出典の信頼性と原本を十分に検証した会員台帳だけを、既存 `identity_source_ledger.py` の `membership_rows` に渡す。現行の候補JSONを直接流してはならない。
4. 非トークン条件は盤面インスタンスの証拠が不足しているため本工程の収集対象外。元データ・所持・禁止制限を変更しない。
