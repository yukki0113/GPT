# Gen9 EXテーマ所属・非トークン証跡モデル監査（2026-11-17）

## 変更の目的と採用しない推論

Gen9 EXの素材ヘッダーに現れる「テーマ所属」と「トークン以外」の条件を、カード名部分一致・モンスター種別・通常モンスター判定等で暗黙の適格性へ置き換えない。実カード個票・日本語原文・所持・個人デッキ情報は公開GitHubへ格納しない。

- 正本：Drive `MD_CURRENT_HEAD.json` Gen9 / schema v4、HEAD SHA256 `e592b34198c290f59580976b6b861de893e6708596eb9df57b3b6e594643a66a`。
- ZIP SHA256 `0fa5fc724f8ab7671404f9297fb240095127840725d1bfd45a7431357467432f`、SQLite SHA256 `dd1e7d85c55b4ba764110af24d852d886abb787e72e18be2c5fd59ef57243411`。
- ZIP内部に `master_duel.sqlite` 1件のみ、SQLite `integrity_check=ok`、外部キー違反0件。
- 既存Gen9 `card_extra_material_requirements` のXYZ/LINK `UNPARSED` 606件の原文ヘッダー・本文SHAを再照合し、両者の不一致0件。DB原本・Drive HEADは変更していない。

## 厳格な単独文型の観測

| 構文 | XYZ | LINK | 合計 |
|---|---:|---:|---:|
| レベルN＋「テーマ」モンスター×枚数、または「テーマ」モンスターN体 | 26 | 68 | **94** |
| トークン以外のモンスターN体 | 0 | 9 | **9** |
| 合計 | **26** | **77** | **103** |

これは前回の未対応112件中の文型を精査したもので、既存の広義構文観測336件へ103件を単純加算しない。複合条件（属性＋テーマ、同一/異なる条件、トークン除外＋他の限定、候補の一部のみ）は認識対象外に留める。**103件は根拠を要求できるヘッダー数であり、テーマ所属済み／非トークン確認済みの実カード数ではない**。

## 新規実装：厳密な出典付き「申告」モデル

- `engine_m6/identity_material_evidence.py` は完全一致パーサーと、出典紐づけされた **素材の各出現位置単位** の申告診断器。
- 申告束は `master_sqlite_sha256`、`extra_card_id`、`material_header_sha256`、順序対応する `occurrences` を必須とする。
- 各出現位置は `card_id`、`predicate`（`ARCHETYPE_MEMBERSHIP` または `NOT_TOKEN`）、ヘッダー中の厳密な `label`、true/false の `claim`、`source_ref`、`source_document_sha256`、`review_status` を必須にする。
- 同じカードIDの複数枚でも、素材の出現位置ごとに別の申告が必要。トークン性は物理的な候補素材の状態に左右されるため、カード種別だけから `NOT_TOKEN` を推定しない。
- `REVIEWED` は「根拠のレビューを入力者が申告した」意味だけであり、第三者検証・公式性・実際の盤面・召喚可否を保証するものではない。SHAは文書の同一性を固定するが、内容の権威を証明しない。
- 返却値は `UNKNOWN`、`MISMATCH`、`CLAIM_ALIGNED` のみ。**一般の静的 `MATCH`、素材適格性 `verified=true`、`POSSIBLE_ON_PAPER`、実デュエルの召喚成立には絶対に昇格しない**。

## M6-5Bとの接続

- `engine_m6/structured_materials.py` に追加の任意引数 `identity_evidence=()`。従来の `proposed_routes` 必須キーと既定処理は不変更。
- targetの存在・重複・束のキーを検査し、XYZ/LINKのGen9 `UNPARSED` にだけ適用。該当のヘッダーに整合する証跡があっても `screen=REQUIRES_REVIEW`。
- 束未入力時は従来診断を保持する。誤ったソースSHA、対象カード違い、出現位置の根拠不足、異なるラベル、未レビューは `UNKNOWN`。ゲーム上の成功・同時確保・規制適合の各確認済みフラグは常にfalse。

## 合成反例・保全

- `engine_m6/tests/test_identity_material_evidence.py`：架空カード・架空文書SHAのみを使用し、所属申告のtrue/false、非トークン状態、同カードID複数出現、出現位置不整合、SHA不一致、レビュー不足、複合ヘッダー拒否、旧APIの互換性、M6-5B `REQUIRES_REVIEW` 維持を検査。
- 現段階で**公式なテーマ所属台帳・ライブ盤面トークン台帳は存在確認できていないため、実カード103件を検証済みにすることはしない**。
- 本番Drive ZIP、SQLite、HEADは不変。所持184種、禁止制限215件を保全し、Gen10へのスキーマ昇格は行わない。

## 次のゲート

1. 公式出典からカードID対テーマ所属の版付き一覧・ソース日時・文書バイトSHAを取り込み、抽出ルールと反例を第三者検証できる形にする。
2. トークン性は盤面の素材インスタンスID、生成元、出典イベント、時点を別スキーマで表現し、一般カードIDを非トークンの証明として扱わない。
3. 上記の両資料の検証ができるまでは、`CLAIM_ALIGNED` は「申告相互の整合」であり、静的素材適格性も未証明としてレビューを必須とする。
