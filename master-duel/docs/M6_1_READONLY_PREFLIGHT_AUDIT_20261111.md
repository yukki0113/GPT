# M6-1 受入監査 — 非公開正本のread-only Preflight（2026-11-11）

## 判定

**M6-1: 取得・SHA照合・全登録所持列挙 PASS。テーマ固有採否・現行MD合法性・生成CP/残高判定は PARTIAL / 未着手（後続M6-2〜M6-4）。**

この区別は必須。登録済み所持135種類の**存在・状態・レア・規制候補**をすべて読めたことは、135種類すべてのデッキ別採用理由を確定できたことを意味しない。

## 実装

- `engine_m6/preflight.py` — `preflight_from_verified_bytes`。Driveフォルダで呼出側が再発見したHEADの**取得前/後生バイト一致**・外部期待SHAを要求。HEAD内のZIP/SQlite SHAを独立チェック。ZIPの1メンバー制約、SQLite `mode=ro&immutable=1`、`integrity_check`、FK検査。
- `inventory JOIN md_catalog`の全登録行を一意card IDでソートし、`known_state`・`owned_count`・MDレアを照合。登録件数とJOIN結果数が一致しない場合は例外。
- 採否のオーバーライドが未指定なら、全登録カードに`REVIEW_REQUIRED`＋理由を付けて`preflight_status=PARTIAL`。テーマを知らない段階で`ADOPT`を捏造しない。オーバーライドは登録済みカードIDに限定し、ADOPT所有枚数の過大計上を拒否。
- M3の候補上限0を現行確定規制に昇格せず、**候補0を採用しようとするとfail-closed**。現在のM3は`UNVERIFIED_SOURCE`でありゲーム内確認が必要。
- CP policyは各レア30CP+`USER_CONFIRMED`であることと**外部期待SHA**を検証。C5 sidecarはM5正本`open_sidecar`の外部期待ZIP/manifest SHAと元DB SHAで照合。所持デッキcatalogは参照する場合のみ外部期待SHAを要求、デッキ内枚数を所持数とみなさない。
- `SourcePins`へ各readback SHA、HEAD/ZIP/所持/M3世代、M3版・CP版・M5版・不足理由を受け渡す。M4/M5-A/Bを本工程で直接取得していない場合は`PARTIAL`、`PINS_PRESENT_NOT_BYTES_VERIFIED`への無断昇格なし。
- M6-1は**ネットワークI/Oを含まない**決定的bytes-in検証器。最新HEADのDrive再発見、独立取得、二度目のHEAD読み戻しは呼出側の責務で、実運用で省略不可。実DBに対する正式moduleの完全なランナー接続はM6-6の追加対象。

## private Drive 実データ監査

実際にDriveフォルダを再一覧して現行HEADとC5サイドカー、CPポリシー、別系統所持デッキcatalogを発見し、HEAD、ZIP、C5のZIP＋manifest、CP、所持デッキcatalogを独立取得。SQLiteを読取専用で照合した。操作前後にHEADを再取得し、**生バイト一致**。これは公開moduleの合成試験とは別の独立privateスモークであり、正式moduleがprivate本番データと接続されたという受入とは区別する。

| 項目 | 確認値 |
|---|---|
| 本番HEAD | Generation 5、raw SHA `0799c1d946bf31f10fd92187e933ebaa17caa4aea16994a60c72d55f7e4949d9` |
| Snapshot ZIP | `f8bc126ebf9335e8aa3cd9ffaaeceb2afd7bb8d944d13bfd5d5ba389b0b0f573` |
| SQLite本体 | `662f905fe9fe3f6b41d26c33e8780bd920743e6348903cd0d53bcb99ce77a289` |
| カード | 13,948種類 |
| 所持登録 | 135種類 / 135行照合 |
| 所持状態 | KNOWN_POSITIVE 66、KNOWN_ZERO 69、UNKNOWN 0（未登録カードはUNKNOWNのまま） |
| 所持登録カードのレア内訳 | N 5、R 16、SR 53、UR 61 |
| MD禁止制限 | 2026-11-05版215件、すべて`UNVERIFIED_SOURCE` |
| 所持内のM3禁止0候補 | 10種類、要公式確認/採用保留 |
| CP方針 | 各レア30CP、`USER_CONFIRMED`。raw SHA `47fb498b55df2e6b95d46a04e14f7a2ce1946a9ebad91a7b8ca9a062900614f9` |
| M5-C sidecar ZIP | `f3a5c4798fb3ce8b4c78e9c9ea2a704ad34dfb5fb5eb70aea1c5c76c10d09e53` |
| M5-C manifest | `fddc571438e6692a826f99ada813e794027ae34ebc3059ddd1d771169a57b3db` |
| 所持デッキcatalog（別系統） | `cca6ac4b7d9b939f6b91f28b84cdd6b6fc372c87f73a51522081fce91364b141` |

現段階ではデッキの採用判断をしていないため、135種類を`REVIEW_REQUIRED`で保存。規制候補0の10種類は、公式未確認を明示した要確認理由付き。

**private Drive監査ファイル**：`MD_M6_1_PREFLIGHT_PRIVATE_AUDIT_20261111.json`、43,506 bytes、SHA256 `8a37c39e189ec23d9826edd551d09a4b63e20422e0815ba9091f84380d4cb845`、Drive ID `1okXpHVw6yVKNQSDJV3eXaSHtZXXOE_2m`。アップロード後に**別要求で読み戻し、保存前のSHAと一致**。カード別監査はここにのみ保存。公開Gitに個別所持行を置かない。

## 合成CI

`engine_m6/tests/test_m6_1.py`：**19件追加**。架空DBを使いHEAD変化、ZIP改変・不正メンバー、CP・所持デッキcatalog外部SHA不一致、所持未登録の推測、所有数超過、M3候補0の誤採用、C5原本SHAミスマッチ、全行数などを検査。

[GitHub Actions run 42966768867](https://github.com/yukki0113/GPT/actions/runs/42966768867)：**M6 54件・全体427件（既存1スキップ、失敗0）**。先行CIでテストfixtureが新しいCP SHA引数に未追従し一時失敗したが、原因修正後の最新runはSUCCESS。放置・合格偽装なし。

## 残課題

1. **M6-2**で具体的なテーマ別候補・M5-A/Bを統合し、135件の`REVIEW_REQUIRED`をカードごとの`ADOPT/CONSIDER/EXCLUDE`に置換。これまでは`preflight_status=PARTIAL`。
2. M3の候補規制は公式MDゲーム内確認が未完で、正式合法性は断定しない。
3. M4/M5-A/Bの個別索引のraw SHA検証、完全なM6統合ランナーおよびデッキ生成は未完。後続M6-2〜6で段階実装。
4. 本番HEAD・所持台帳・M5-C成果物・所持デッキcatalogは書き換えていない。
