# M6-5B Gen9限定XYZ/LINK素材適格性診断の接続監査（2026-11-17）

## 実装範囲

- `engine_m6/material_eligibility.py`：既存のGen9素材ヘッダー観測結果と、仮想素材カードIDの `card_attributes`、`card_monster_types` を照合する静的診断器。
- `engine_m6/structured_materials.py`：既存 `UNPARSED` から限定付き素材ヘッダーを認識できた場合に、`MATCH` / `MISMATCH` / `UNKNOWN` の診断理由を `review_reason` に接続。
- `engine_m6/tests/test_qualified_material_eligibility.py`：架空カードのみで一致・属性/種族/レベル/素材数不一致・LINK換算・テーマ条件未証明・型条件・根拠欠如・原文SHAピンをテスト。
- **すべての追加診断結果は `REQUIRES_REVIEW`**。既存M6-5Bの `POSSIBLE_ON_PAPER` 成立条件は緩和しない。正式な召喚ルート・同時確保・制約適合の検証ではない。
- `material_card_ids` はユーザーまたは外部資料に裏付けられた仮想ボード入力に限り、所持カードから自動生成しない。カードIDの同一値重複は複数枚の物理カードを表し得るが、同時保有の証拠とはみなさない。

## Gen9 private実カード：構文観測の静的述語サポート範囲

現行Gen9の `grammar='UNPARSED'` のXYZ 221件・LINK 385件を出典ヘッダーで再走査。直前に確認したHEAD/ZIP/SQLite SHAに固定し、card本文・個票は公開しない。

| 種別 | 限定構文観測 | 属性型 | 種族型 | 通常/効果型 | 現状未サポートの限定語 |
|---|---:|---:|---:|---:|---:|
| XYZ | 131 | 45 | 60 | 0 | 26 |
| LINK | 205 | 24 | 68 | 3 | 110 |
| 合計 | **336** | **69** | **128** | **3** | **136** |

**200件**は、現行DBの属性・種族・モンスター詳細種別に対して静的な素材適格性の照合を試みられる文型。**136件**は、テーマ所属・トークン除外等の未証明または未対応の限定語を持つため、現時点では不明を維持する。この表は素材選択結果や召喚可否の個別確認件数ではない。

- 属性・種族・レベルの照合は、元カードに登録された値が一致するかのみ評価する。
- LINKは最低/最大素材数、個々のリンク素材の換算値、対象モンスターのリンク値も照合する。
- 属性・種族・種別に欠損がある場合はUNKNOWN。判定可能な不一致のみMISMATCH。
- 正式テーマ所属をカード名部分一致から推測しない。トークン除外・代替召喚・相互関係・特殊召喚ロックは未検証のまま。
- 「静的条件MATCH」は召喚成立を意味せず、必ずREQUIRES_REVIEW。

## 保全と未完了

- 本番Drive HEAD、Gen9 ZIP、SQLite、所持184種類、禁止制限215件を変更していない。
- 将来、厳格な `POSSIBLE_ON_PAPER` 判定へ進める際は、別途ソース固定の素材供給・同時確保・召喚方法・全制約の根拠を要求し、実カード回帰と反例を追加する。
- 既存Gen9の `grammar` 列は変更しておらず、336件のソース観測のみを利用している。

## GitHub最終回帰・不具合修正

- 初回の合成テストが、同一カードIDを複数素材として指定したケースでSQLiteバインド数不一致を検出。既存M6-5BのID重複解消をSQL検索用だけに限定し、素材枚数は変更しない修正を実施。
- 最終ソースコミット：`c7c99bd1bc40903c1984eace6f8905ce66da4ac5`。
- [Python regression run 44049256127](https://github.com/yukki0113/GPT/actions/runs/44049256127)：**SUCCESS**、engine_m6 **321 tests PASS**、全体 **699 tests / 1 skipped / PASS**。
- [M6-8 runtime bundle run 44049255843](https://github.com/yukki0113/GPT/actions/runs/44049255843)：**SUCCESS**。
- 結果はGitHub Actionsのジョブとログから確認。合成テストとprivate実データにおける分類集計は別の証拠であり、private実カードごとの召喚ルート成功を意味しない。
