# M6-5 受入監査 — 候補比較・所持全件理由・EX補強・private不変提案（2026-11-11）

## 完了判定

**M6-5 PASS：実装・合成CI・非公開ソース独立比較とprivate不変保存**。M6-5で完成デッキの推奨・実ゲームの合法性やM3公式確認・自動的なEX補充・全工程の本番実データ一気通貫実行はしていない。M6-6とM6-7は別工程。

### 実装内容

- `engine_m6/report.py`：M6-3 `DeckCandidate`、M6-4 `Evaluation`、M6-1の**登録済み所持カード全件**を結合。カードが採用されない場合も、登録されている各card IDに`EXCLUDE`と「根拠付き候補には入っていないだけで相性が悪いとは言えない」という理由を残す。採用カードは`ADOPT`だが、**所持済みと同義ではない**。採用中の所持未登録カードはUNKNOWNで別掲し、所持0枚にしない。カードごとの出典・必要CP上下限・3つのUR0判定・M3警告を比較し、`recommendation_eligible=false`を維持。
- `extra_gap_review`：EX採用7枚であれば未使用8枠、比較対象が15なら0枠と区別。EX候補にはカードID/EX区画/MDレアリティ/出典/効果検証/規制検証/採用役割/対応ロック検討が必須。**出典のない自動補充は禁止**。非URであっても効果成立・召喚条件/ロックを確認済みとしない。
- `engine_m6/proposal_store.py`：採用判断・未採用理由を含む比較を、固定ZIP・JSON canonical構造とSHA256 manifestへ変換。検証時に外部でピンした**ZIP、manifest、元SQLiteの期待SHA**をすべて必須とし、メンバー個別SHAと構造を確認。`save_new_private_proposal`は新規不変ファイルのみ作成し、上書きを拒否。本番HEAD/カードマスター/所持台帳/登録済みデッキは更新しない。
- M6-4からの軽微な不具合修正：本番所持台帳で**同じカードを4枚所有している例**を発見。デッキ採用は3枚上限だが、所持枚数まで3枚上限にするのは誤り。`evaluate.py`の所持数バリデータを修正し、追加の合成回帰を含めた。

### 合成CI

`test_m6_5.py` 20件＋M6-4所持4枚負例追加1件。出典なしEX、UR0条件に反するEX、同一候補混入、SHA改竄、元DB世代不一致、全件所持監査漏れ、提案ZIP上書き、外部SHA未一致、元入力非破壊を検査。

[GitHub Actions run 42981340998](https://github.com/yukki0113/GPT/actions/runs/42981340998)：**M6全138件PASS、全体511件／既存private fixture1件スキップ／失敗0**。最終ドキュメントとPRコミットも別途CI確認する。

## private実データを使った独立比較

**実装全体をprivate本番データで直通実行したM6-6受入ではない**。M6-1の全件所持監査・M6-3のsource-era候補・M6-4のcard行を独立のread-only比較で再構成し、実装済みの`proposal_store.py`で実際の不変ZIP生成・独立読戻しを試験した。カード個票はprivateのみ。

- 本番HEAD **Generation5**、元SQLite SHA `662f905fe9fe3f6b41d26c33e8780bd920743e6348903cd0d53bcb99ce77a289`。M6-4の評価card-rowsとmanifestを再検証。
- 所持登録135種類は**両候補の採用/見送りに関係なく全件評価**。ただし役割に対する「採用しない理由」は既知候補/出典に含まれなかったという意味であって、ゲーム内性能や他テーマとの非相性を証明しない。
- MD禁止制限の候補は`UNVERIFIED_SOURCE`。公式の現行MD合法性、生成可否、CP残高、必須中核と対戦成立は未検証。

| private集計 | 軍貫 掲載版 | 軍貫 UR0仮説版 |
|---|---:|---:|
| MAIN/EX | 40/15 | **40/7** |
| 採用UR | 20 | **0** |
| 登録済み所持カードのうち候補に登場 | 6種類 | 3種類 |
| 登録済み所持カードのうち候補に不採用 | 129種類 | 132種類 |
| 採用したが所持が未登録 | 23種類 | 16種類 |
| 新規UR不足 | 2〜11枚 | **0〜0枚** |
| 未使用EX枠 | 0 | **8** |
| 比較上の推薦確定 | 不可 | 不可 |

### EX7→15候補の実際の検証結果

元のEX15からUR0案のEX7に含まれない8枚を差分監査した結果、**7枚はUR、1枚はSR**。そのSRのカードは《Ｎｏ．３９ 希望皇ホープ・ダブル》（`konami:14220`）。現在のprivateカード本文（MD由来、verification `UNVERIFIED_SOURCE`）には、**レベル4モンスター2体**、効果を利用するための**《ダブル・アップ・チャンス》**、および「希望皇ホープ」Xモンスターへの重ねるX召喚が記載されている。

UR0仮説版のMAINに《ダブル・アップ・チャンス》（`konami:9663`）はなく、EXに他の「希望皇ホープ」Xモンスターもない。したがって**SRだからという理由だけで追加しても既存効果ルートが機能すると言えず、保留が妥当**。旧掲載版で採用されるUR群をそのままUR0案へ戻さない。M6-5の候補は`PENDING`、`automatically_added=false`、`role_coverage_verified=false`で保持する。残り8枠を埋めるための一般カード探索・属性/ランク/展開相性調査は今後の構築候補再検討で必要。

## private Drive保全と独立読戻し

以下3件をprivate `GPT/MasterDuel/DB` に**新規保存**。別のDrive取得要求でZIP・manifest・監査サマリーをそれぞれ取得し、元バイト列とSHA256が一致。ZIP全メンバーの内部SHA検証と元SQLite外部SHA検証を実施。既存source HEAD、所持デッキcatalogは未変更。

| 成果物 | バイト | SHA256 | Drive ID |
|---|---:|---|---|
| `MD_M6_5_PRIVATE_PROPOSAL_20261111.zip` | 4,376 | `1df3a77b82388d195cbac8b1101852c2675bc6744b897a0f6c1234647a4f64fe` | `18o2zANarNASuEAGhHZ3m2_52rhYPsDGr` |
| `MD_M6_5_PRIVATE_PROPOSAL_20261111.manifest.json` | 497 | `ece91466ebdaff21fb3efd1fe8e3a4c8e2744b706efe230303873e98b9e36bb2` | `1QF5uvPPWngtar6MzdkSnmVvdbeBVvxwr` |
| `MD_M6_5_PRIVATE_AUDIT_SUMMARY_20261111.json` | 2,119 | `5337699c196f9f63f2fdd513ff61da750c662925a4ce606c1568fc65cbc30c6c` | `1oHs7IquJ103eEp9MRSufGe4V_4Xn0D64` |

## 次の工程

M6-6では今回の合成機能とprivate実データを**同一実行経路**で接続し、HEAD再取得からSourcePins、候補生成、費用計算、全件所持理由、ZIP manifestの独立保存まで一気通貫で検証。M6-7でデッキ構築専用スレッドにて受入。EX補強は未確定の依存カードを勝手に挿入せず、明示的に出典と必要MAIN/EXパーツを再検査する。
