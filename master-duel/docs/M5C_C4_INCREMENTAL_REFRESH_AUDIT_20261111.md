# M5-C C4 — 差分再検証・キャッシュ・版保持 受入監査（2026-11-11）

## 完了判定

**C4 PASS（差分更新計画・限定失効・append-only ステータス・版管理・非公開Drive往復）**。C3までの実カード個票を読み取り専用で照合し、**現実に更新が発生したという主張ではなく、変更イベントを仮定した5ケース**で再調査範囲を検証した。実サイトの変更監視、自動スクレイピング、実MD禁止制限の公式更新確認、C5完成Bundleは本工程に含まない。

### 公開コード

- `engine_m5/refresh.py`：
  - `build_index(bundle, variants)`: SOURCE→claim/recipe/route/variant と CARD_ID→依存オブジェクトの索引。転載元`derived_from_source_id`を辿る。参照不正や重複を拒否。
  - `deterministic_cache_key(profile, source_revision, card_text_sha, banlist_effective_on, extractor_version)`: canonical JSONのSHA256。実取得日時だけではキーを変えない。`UNKNOWN`記事版やSHA形式不正はキャッシュヒット不可。
  - `plan_refresh`: ARTICLE SOURCE_REVISION／CARD_TEXT_SHA／BANLIST／USER_REPORT／NEW_CARD／INCOMPLETE_BUNDLE／EXTRACTOR_VERSIONのイベントを分類し、影響対象と作業型を決定。`batch_limit`で処理枠上限、超過は`pending_queue`に欠落なく保持する。
  - `make_staleness_overlay`: 元知識canonical SHA照合後、影響を受けるroute/recipe/claim/variantを**STALEまたはREVIEW_REQUIREDの独立overlay**として記録。元のゲーム検証状態を黙って書換えず、旧C3版を不変に保持。M6はC5でoverlayをブロック条件として読むこと。
- **禁止制限差分**：変更カードIDが判明したときは対象recipe/variantのM3再照合を要求し、記事本文の不要な再取得は行わない。施行日だけ更新され、変更カード集合が不明なら全recipe/variantをREVIEW_REQUIRED。UNKNOWNを「無変更」として扱わない。
- **効果本文SHA変更**：対象カードを使用するrouteのみ`RECHECK_EFFECT`、そのカードを含む掲載recipeや関連variantは別タスクで注意喚起。ゲーム内成立を推測しない。
- **記事改訂**：同一検証済みrevisionの再処理を省略。変更時は該当出典のclaim/recipe/route/variantと元記事の二次派生物だけ再調査。実際の記事は再取得していないので、今回の同一版は**試験入力**であり2026-11-11現在のサイト無変更を保証しない。

### private実データ差分リプレイ

入力のprivate正本：
- C3 knowledge Generation相当version3：SHA `8812f23d07b616168de9326d6c991e8f422aa68adfddb93b4a9b9414415a9be0`（58,003バイト）。
- C3 軍貫UR0 variant：SHA `eec847b4ee58af08ac39580dcdb1d9532e2691e76a3288ff9c67c00f40c9f202`（15,424バイト）。
- 非公開カードHEAD：Generation5、SQLite SHA `662f905fe9fe3f6b41d26c33e8780bd920743e6348903cd0d53bcb99ce77a289`。読み取り・既存ID照合のみ。

| 仮定したイベント | 影響対象の試験結果 | 再調査 |
|---|---|---|
| 同一の既知記事版 | 0件 | キャッシュSKIP（同一PIN前提） |
| 軍貫記事の新版を仮定 | 軍貫のclaim/掲載recipe/UR0 variantの3件 | 出典再抽出＋候補再評価 |
| イビルツイン初動カードの本文SHA変化を仮定 | その効果を使用するrouteと掲載recipeの2件 | M4効果再照合、recipe注意喚起 |
| 軍貫中核カードを含む規制変更を仮定 | 軍貫の掲載recipeとUR0 variantの2件 | M3の新規制日評価のみ |
| 施行日だけ新しく変更カード集合不明を仮定 | 全掲載recipe2件＋variant1件 | 保守的REVIEW_REQUIRED |

**これらは変更の実発生を証明するものではない**。効果変更先SHAも架空値、規制施行日も仮想入力。実サイト・公式制限の現状を示すレポートではない。

### Drive保存・独立読み戻し

private `GPT/MasterDuel/DB/` に新規ファイルを保存。**別API要求でダウンロードし、元のローカルバイト列/SHAおよびmanifest参照SHAが完全一致。** C3の旧版は上書きしない。

| ファイル | バイト | SHA256 |
|---|---:|---|
| `MD_M5C_C4_KNOWLEDGE_20261111.json` | 58,611 | `511675bd541fe243ae79d9419b98caa13256922957294040103434f20b2d7db6` |
| `MD_M5C_C4_REFRESH_REPLAY_20261111.json` | 2,871 | `a4a37fd4a9c6ecc8618b7e44c51e9056beaf7b61e4b53bb520172d4715fdd579` |
| `MD_M5C_C4_KNOWLEDGE_MANIFEST_20261111.json` | 731 | `a1b78e63ba55a46592b205c2735f5b7fb288f9bcae6ea85cf6dea16f9e493629` |

DriveファイルID: knowledge `186I-fkr0m-IoZ3z0m9JTPs-r-A-Yllza`、replay `1oTeGtDuGKipf0zssaYYKjeNervN7z4G4`、manifest `1iS0A5c5fJzhNAP77OVrL4EdPwErbiXpB`。

### C4未検証事項・C5への持越し

1. 現行記事・禁止制限の**自動監視や定期取得は未実装**。変更イベント供給元の信頼性を管理し、実際の差分がある場合のみ発火するのは利用側の責務。
2. 変更されたカードの効果のルール上の意味が同一である保証はない。C2再検証・M3規制再評価後に限りSTALEを解除可能。
3. C4の`overlay`は読み出し側で照合して初めて推薦をブロックできる。**C5でprivate ZIP/manifestとM6向けBundleのステータス検証を実装するまでは、実装済みの自動推薦を意味しない**。
4. sourceのrevision/内容SHA自体が`UNKNOWN`なら確定キャッシュ利用は不許可。C1収集記事の多くはcontent_hash未取得なので、実運用での再取得削減率は現段階では算出しない。
5. 既存の`MD_CURRENT_HEAD.json`、汎用所持台帳、所持デッキ索引、C3 knowledgeは未変更。公開Gitには個人のデッキ個票やカード採用行を追加しない。
