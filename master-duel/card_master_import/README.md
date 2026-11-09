# JSON → SQLite カードマスター（検証用）

Python 標準ライブラリ。公開 Git に JSON、実カード効果本文、個人データ、DB を置かない。P1-A1 NO-GO。本番 HEAD は更新しない。**2026-11-10 Work側でDrive原本2件のSHAを再照合し、実JSON全13,948件を独立クロスウォーク・ローカルSQLite ZIP化して整合性検査PASS。** Codex Cloud自身の実データ実行ではなく、GitHubのこの版の実装とWork側の検証用変換処理は区別する。コードへ実形式（MD文字列の数値、`types`、未知攻守`?`）に対応する修正を含める。 実入力で不一致が出た場合は中止し、出典と入力型を監査してから修正する。

`master-duel` から `python -m card_master_import /private/master-duel-raw.json /private/cards.json` で SHA 固定の dry-run。異なる SHA は別版として拒否。集計は入力名・SHA・件数・一致方式・未解決・ID重複・欠損・不正・UNKNOWN のみ。完全一致、正規化候補の種別・属性照合、明示された同名例外以外の曖昧な候補は保留。Yugipedia ID は使用しない。MD の `craftable=No` 以外は UNKNOWN。読み仮名の `<rt>` は表示名から除外し、本文は格納しない。入力が未知の構造・型の場合は安全側に失敗する。

空の検証用 schema v1 ZIP を用意し、同じ入力版で集計がすべて正常な場合だけ `--base-zip /private/base.zip --output /private/candidate.zip --acquired-at 2026-11-10` を付ける。新規パスにのみ出力し、元 ZIP は編集しない。SQLite への書き込みは一括トランザクション。既存カードとの名前・ID・属性・レアリティ・入力 SHA の不一致は拒否。所持・履歴には触れず、P2 backup・ZIP 検証を実施。出力は P1-A1 の審査用で、本番に昇格しない。

Drive 正本の解決と SHA 検証、私的な検証用スナップショットの新規保存と独立読み戻しは別工程。Drive 認証・保存・HEAD 更新は本モジュールでは行わない。

テスト: `python -m unittest discover -s card_master_import/tests -v`。13,948 行のテストは合成であり、実データの成功を意味しない。

## 実JSON由来の形式差（2026-11-10）

MD rawのモンスターは `card_type` がなく `types='Dragon / Effect'` 等の文字列。魔法・罠は `card_type`。MDの level/rank/atk/def は文字列で、OCGカード側は整数。ATK/DEFの `?` は `NULL` として扱い、0と混同しない。種族はMD `types` の先頭要素。Work側の元JSONを使う独立クロスウォークでは `exact=13931`, `normalized=13`, `exceptions=4`, `joined=13948`, `unresolved=0`, `duplicate_konami_id=0`, `missing_ja=0`; レア分布 N=5318, R=4038, SR=2954, UR=1638。検証用ローカルSQLite（カード13,948、所持0）でintegrity/foreign key OK。実入力に対する**PRコードそのものの回帰再実行と再確認**は別途必要。本番HEADは不変更。
