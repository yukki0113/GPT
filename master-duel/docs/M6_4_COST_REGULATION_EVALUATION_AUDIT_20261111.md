# M6-4 受入監査 — 所持・規制・CP・UR0条件の独立評価（2026-11-11）

## 判定

**M6-4 PASS（合成実装とprivate実データ独立ソース監査）**。 `engine_m6/evaluate.py` は源泉SHAを指定したSQLiteをread-onlyで照合し、構造候補のUR条件・所持確定数・未登録UNKNOWN・生成CP範囲・規制候補の未確認状態・EX未使用枠を評価する。**最新HEADの実発見やユーザーへの完成推薦は本関数だけでは実施しない**。M6-5比較・保存、M6-6新モジュールでの実データ統合受入、M6-7利用者スレッド受入は未着手。

- GitHubに個人所持/実デッキの行は公開しない。今回の実行ログ・監査集計のみ公開。
- M6-4はM6-3 `DeckCandidate` schemaを検証し、SQLite raw SHAを外部ピンと照合する。CP方針も**JSONオブジェクトの値だけでなく元のrawバイトSHAを要求**し、USER_CONFIRMED・4通貨各30CPを適用する。
- 制限判定はMD_STANDARD snapshot ID/施行日/検証区分をピンに照合。M3の215件は未検証候補であり**公式の合法枚数として代入しない**。候補の超過は `UNVERIFIED_BANLIST_CONFLICT` の警告、正式GAME_VERIFIEDからの超過はBLOCKED。候補に載っていないカードの規制限度もUNKNOWNであって3枚確定とはしない。
- 所持 `KNOWN_POSITIVE`/`KNOWN_ZERO`は実枚数に照らし不足が確定。未登録`UNKNOWN`は最低不足0・最大不足採用数の幅として計上し、無料/所有0枚とは断定しない。生成可否がUNKNOWNなら生成できることも保証しない。
- `CORE_UR_ZERO`、`NEW_UR_CRAFT_ZERO`、`STRICT_NO_UR`を独立したPASS/FAIL/INDETERMINATEで返す。COREが未検証ならLOW_RARITY_CORE全体はたとえUR0でもINDETERMINATE。UR新規生成0が明確にFAILならCORE状態にかかわらず要求モードFAIL。
- 予算は選択した`UR_BUDGET`/`CP_BUDGET`のときのみ参照し、未指定の予算キーでクラッシュしない。SR CPでUR CPを補填しない。
- 明示された`cp_balance`がない場合、必要額と残高の照合はINDETERMINATE。ユーザーに確認のない残高を仮定しない。
- MAIN40–60/EX0–15の構造はM6-3の証拠付きcandidateを再検証。**EX7枚は合法な下界の構造**だが、`EXTRA_DECK_UNUSED_SLOTS_NOT_OPTIMIZED`（未使用8枠）を常に残す。未登録のEX新採用・ゲームロック・必要出張の検証はM6-5以降の比較材料。

## private SQLite / C5 元データを用いた独立再評価

本節は、**M6-4本体をprivate実環境で全ソース統合実行した結果ではなく**、最新Generation5 SQLiteとM6-3 source-era候補の独立read-only監査で算定した結果。公開合成回帰とは区別してM6-6の統合受入を先取りしない。

- 正本HEAD Generation5、SQLite SHA `662f905fe9fe3f6b41d26c33e8780bd920743e6348903cd0d53bcb99ce77a289`、C5 sidecar ZIP SHA `f3a5c4798fb3ce8b4c78e9c9ea2a704ad34dfb5fb5eb70aea1c5c76c10d09e53`。
- 実データのCP policy `USER_CONFIRMED`：N/R/SR/UR 各30CP/枚。利用可能CP残高は確認していない。
- 依存しているM3 snapshot は2026-11-05候補で `UNVERIFIED_SOURCE`。正式な2026-11-11 MD禁止制限への適合性は未確認。

| 集計 | 軍貫 掲載例 | 軍貫 UR0仮説版 |
|---|---:|---:|
| MAIN / EX | 40 / 15 | **40 / 7** |
| 採用UR枚数 | 20 | **0** |
| 所持登録済カード種類 | 6（所持あり5、所持0が1） | 3（所持あり3） |
| 未登録で所持UNKNOWNの種類 | 23 | 16 |
| URの追加必要枚数 | 最低2〜最大11 | **0〜0** |
| URの追加CP | 最低60〜最大330 | **0〜0** |
| Nの追加CP範囲 | 0〜450 | 0〜420 |
| Rの追加CP範囲 | 0〜150 | 0〜210 |
| SRの追加CP範囲 | 0〜450 | 0〜510 |
| EX未使用枠 | 0 | **8** |
| 未確認M3候補の枚数衝突 | 1カード | 0カード |
| 必須中核UR0 | UNKNOWN | UNKNOWN |
| ゲーム内合法性/展開 | 未検証 | 未検証 |

**重要**：上記のUR20やUR0は、現在のprivateカードマスターに記録されたMDレアリティでの構成上の値。マスターのレアリティ検証が`UNVERIFIED_SOURCE`であることを明示したまま、ゲームで検証済みとはしない。「軍貫UR0仮説版はUR生成0」でも、N/R/SRの所有UNKNOWN・生成可否UNKNOWN・CP残高不明があるため**無料で完成・所有済みだけで構築可能とは言えない**。

### EX7枚への対応方針

EX15枚を埋めること自体が目的ではないものの、EXが7枚で良いというゲーム戦術上の根拠は現段階でない。**UR0を守って最大15枠へ補強できるか**を次の候補比較で独立評価する。既存M5-Cの軍貫C2展開ルートは0件であり、機能/依存/EXロックを実証できない。よって現時点ではEX7枚を「構造的候補・最適性未評価」と明示し、不足8枠を無根拠なカードで自動補充しない。将来の追加カードはM2登録全件から候補を探し、M4効果・M3規制・採用理由・CPを個別表示する。

## private Drive成果物と保全

private `GPT/MasterDuel/DB` に以下3件を**新規保存**し、別のDrive取得要求で生バイト読戻し・SHA256/manifestの相互一致を確認。本番HEAD、所持カード、登録済みデッキの書込みなし。

| ファイル | 容量 | SHA256 | Drive ID |
|---|---:|---|---|
| `MD_M6_4_PRIVATE_EVALUATION_SUMMARY_20261111.json` | 2,796 | `91aebb5496567d850f1aef55f6a1eecaaab53fd6e5d0502474f88425e783ae2f` | `15GJz_dDu4QIV_gUraMmAiUcfZqz6XFv6` |
| `MD_M6_4_PRIVATE_EVALUATION_CARD_ROWS_20261111.json` | 14,963 | `d99c30ab40156d85e778dcc535e57ba33efebdf0a791ef60207f4785b40646f2` | `1e_JURnYoD8mxlN0hZVJx2e0aNOWkMns0` |
| `MD_M6_4_PRIVATE_EVALUATION_MANIFEST_20261111.json` | 454 | `66bfc4f1dabc58f0cc5479d2057b2152e8f330dddc13942ec5bdada85042a2b0` | `1EVkoGQ4jqdYMjfiVb_u6eYLxY0THiHP4` |

## 合成CIと受入境界

`engine_m6/tests/test_m6_4.py` は架空のSQLite・カードID・枚数のみで22件。所持あり/明示0/未登録、UR予算別、CP4通貨、未検証規制候補0、ゲーム検証済みの0制限、SHA改竄、UNKNOWN効果/生成、EX7の未使用8枠、元DB不変を検査。

[GitHub Actions run 42975691495](https://github.com/yukki0113/GPT/actions/runs/42975691495)：**M6 117件PASS、全体490件・既存private fixture1件スキップ・失敗0**。初回失敗時の原因（未指定`UR_BUDGET`項目を事前に評価しKeyError）を分岐の遅延評価に修正して成功。最終監査書コミットのCIも別途確認。

### 次のM6-5

候補比較・EX補強の評価・不採用の所持カード全件の理由出力・private提案の不変保存を実装。EX7から15へ増やせる可能性をカード効果/枠/所有/CPの出典とともに示す。ただし、現行MDの公式制限・ゲーム内動作を未検証のまま確定推薦へ昇格させない。
