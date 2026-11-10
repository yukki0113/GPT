# M3生成可否の非ブロッカー化と禁止制限一次ソース整理（2026-11-10）

## ユーザー決定（運用方針）

- **生成可否 `UNKNOWN` はデッキ候補生成のBlockerにしない。候補を出してよい（`PROVISIONAL_GO`）。**
- 実際にゲーム内で生成不可と判明したカードのみ、例外として非公開レジストリに追加し、必要枚数が不足するレシピを除外する。例外はKONAMI ID・観測日時・報告元・理由を必須とする。
- `UNKNOWN` をDB上で `YES` に書き換えない。`UNKNOWN` のまま暫定GOという*別の運用判定*を返す。
- 既存カタログの `NO` と、後日報告された確定 `NO` は既知の生成不能。すでに必要枚数を所持している場合は、生成不能というだけでは候補をブロックしない。
- 所持不明の場合は所持0と推定せず、`NO` カードが必要になる可能性を注意表示する。実際に新規生成が必要と確定した場合はブロック。
- 正規の禁止制限違反、レシピ枚数や0UR条件違反などのハードエラーは従来どおり保持。候補を生成できることと、デッキ合法性/予算充足の*確定*は明確に別。

## 禁止制限の一次情報源

1. **一次資料**: KONAMI『遊戯王 マスターデュエル』ゲーム内「リミットレギュレーション」一覧（現行適用上限）とゲーム内「お知らせ」（施行日/変更理由）。
2. **一次告知の補助**: KONAMI運営『遊戯王 マスターデュエル』公式X https://x.com/YuGiOh_MD_INFO 。2026-10-26に2026-11-05版を予告した発信が公開で確認可能。
3. **二次資料**: Master Duel Meta、Game8等の改訂記事、YAML Yugi由来の一覧などを照合に利用。OCG/TCG/ラッシュデュエルの公式一覧は**MDの規制一次情報ではない**。
4. **現在のSQLiteに取り込んだ素材**: Drive `GPT/MasterDuel/source/current.vector.json`。215件（禁止114/制限77/準制限24）、2026-11-05版。原本にKONAMI全件出典の証明がなく、`UNVERIFIED_SOURCE` のまま保持。ゲーム内で215件すべてを確認したという意味ではない。

公開根拠: KONAMI公式Xの2026-10-26告知（https://x.com/YuGiOh_MD_INFO）、[ゲーム内一覧の開き方](https://game8.jp/yugioh-masterduel/423063)、[KONAMIによるMaster Duel規制の説明](https://www.konami.com/games/corporate/ja/news/topics/20220427/)。

## コード変更と受入条件

- `regulation_m3/craftability.py`：例外スキーマ検証、`record_exception`（同一ID再登録は冪等）、SHA付きプライベート例外JSON読込、`assess_craftability_gate`（デフォルトは`PROVISIONAL_GO`）。
- `regulation_m3/evaluation.py`：従来の厳密な `status` はINDETERMINATEなどのまま保持。追加の `craftability_gate`・`candidate_recommendation` はUNKNOWN生成可否のみを非ブロッカー化する。明示NO＋確定した新規必要枚数を `UNCRAFTABLE_SHORTAGE` で拒否する。
- `regulation_m3/bridge.py`：HEAD/ZIPのSHA、CPポリシーのSHAに加え、オプションの生成不可例外JSONとそのSHAを検証して評価へ渡す。私的HEAD/SQLiteへの書込みは行わない。
- `regulation_m3/tests/test_craftability.py`：UNKNOWN仮GOとカタログ不変、NO不足阻止、所持充足ならGO、所持不明の保留、私的例外登録の冪等/出典検査、厳格モード、SHA改竄防止、実レシピAPIとの結合。

## 私的台帳と現状

- 例外の正本（初期空集合）: Drive `GPT/MasterDuel/DB/MD_CRAFTABILITY_EXCEPTIONS_20261110.json`。Drive ID `1lM2V0_hKGjQ4WVmDtCRUIteYox21xG3t`、SHA256 `5fe8dbc037d4a4449d94fa264610cbd39aa0f4d5da48864c950d8934e51e9ac2`、147 bytes。別取得SHA照合済み。ユーザーからの個別例外報告はまだ0件。
- 本番DBの `craftable` 集計は2026-11-10時点で `UNKNOWN=13,931 / NO=17 / YES=0`。既存NOは暫定ポリシーの対象外、UNKNOWNだけを候補生成で許容。
- SQLite本番HEAD世代3、所持5種類/計9枚、禁止制限215件はいずれも不変更。新たな例外登録があった場合は、単一ライター・版付け・読み戻しを前提にこの私的例外JSONへ記録する。
- 実装コミット `1fa2f5aaec433575d01533b24e0ab8db55202d36` のGitHub Actions [run 42761905701](https://github.com/yukki0113/GPT/actions/runs/42761905701) は**成功**：全174件、M3=64件、失敗0・スキップ1。追加の `test_craftability.py` 10件は全PASS。
- 非公開Drive初期台帳を別取得で読み戻し、147 bytes / SHA256 `5fe8dbc037d4a4449d94fa264610cbd39aa0f4d5da48864c950d8934e51e9ac2` と一致。
- 追加受入 `test_bridge.py` の「NO例外をSHAピン付きで読んで不足時にHOLD」「SHA不一致・片方指定の拒否」も **GitHub Actions [run 42762127981](https://github.com/yukki0113/GPT/actions/runs/42762127981) で成功**。全176件、M3=66件、失敗0・スキップ1。コミット `2196ce6107abc5d7f830b3830c1c76944afe59f0`。


## 最終読み取り監査

- 非公開Driveの世代3本番ZIPをローカルの読取専用SQLiteとして展開し、HEAD記載ZIP SHAと一致。cards=13,948、card_texts=13,948、inventory=5、inventory_history=5、banlist_snapshots=1、banlist_entries=215、MD craftable UNKNOWN=13,931/NO=17。SQLite integrity=ok、FK違反0。
- この工程で本番HEAD・本番ZIP・所持データは変更していない。禁止制限215件のGAME_VERIFIED昇格もしていない。
