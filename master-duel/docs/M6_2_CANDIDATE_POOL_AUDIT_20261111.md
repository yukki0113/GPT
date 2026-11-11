# M6-2 受入監査 — 中核・出張・汎用候補プールと依存関係（2026-11-11）

## 判定と実装境界

**M6-2 PASS（候補収集契約・依存関係解析・不確実性保持に限定）**。M6-3のMAIN40–60完成案生成、M6-4の現行MD規制・所有数量・CP計算、ゲーム内展開保証、手動の構築スレッド受入には着手していない。M5-Cの実ソースについては**別のprivate読取専用監査**を実施したが、全5テーマでM6-2新モジュールの生データ統合実行が完成したという意味ではない。

- `engine_m6/candidate_pool.py`：SHAを照合済みのM5-C `ThemeKnowledgeBundle`のレシピ/UR0候補/展開経路と、外部参照済みのM5-Aエンジン/M5-B効果候補を情報源別に集約。**重複した同一カードの採用枚数を合算しない**。観測元の数量差、必須中核のUNKNOWN、未解決/STALE/CONFLICT、登録済み所持UNKNOWNとKNOWN_ZEROの区別を保持。
- `engine_m6/dependency.py`：パッケージID、必要パーツMAIN/EX、コピー数、代替選択グループ、依存、競合、共有部品、EX最低枠、任意発動時の制約スコープを検査。共有カードは同時利用保証を付けず**必要枚数のmaxという下界**で提示。代替グループは必ず`UNRESOLVED`を残し、制約を無条件に全経路へ適用しない。
- `engine_m6/m5_inputs.py`：M5-AとM5-Bの別private SQLite索引を、**外部期待manifest SHA→ZIP SHA→内部SQLite SHA→read-only + integrity/FK**の順で検証。M5-Aは3パイロットエンジンの明示構造のみ、M5-Bは指定属性/種族に共起する`ACTION`候補のみを上限付きで読み出す。これらを正式なテーマ所属・サーチ/特殊召喚のゲーム上の保証にはしない。
- M5-A/Bの元生成時DBは**Generation3**（SHA `42fa57c5a41e9d41ae7ae064450485d1b18109f45a616528abff9025cd43b654`）、現行HEADは**Generation5**（SHA `662f905fe9fe3f6b41d26c33e8780bd920743e6348903cd0d53bcb99ce77a289`）。両者は異なるため、抽出候補は`STALE_SOURCE_GENERATION`として扱い、M4の最新原文およびM3の最新規制で再照合するまでは推薦に昇格不可。旧索引は検索材料としてのみ利用する。

## 現行privateソース監査

| 入力 | 検証結果 |
|---|---|
| 正本カードHEAD | Generation5、カード13,948種類、所有登録135種類。照合元MD SQLite SHAは上記 |
| M5-C C5 sidecar | ZIP SHA `f3a5c4798fb3ce8b4c78e9c9ea2a704ad34dfb5fb5eb70aea1c5c76c10d09e53`；manifestの全3メンバーSHA一致 |
| M5-A index | ZIP SHA `1befdc561da63b7b3fe29b4bb707f5a5e36cbe9942a9b445f7fff42c9963874e`；内部SQLite SHA `d70238c99ddc1c319ea7a02fdf3798ba3877981a66bf5abec1e9838efb1d5486`、3出張パイロット、integrity/FK PASS |
| M5-B index | ZIP SHA `436499ab5265101ea71cffd14db87f3a2c80d4d2fa7a315d09cae9c017e53ea6`；内部SQLite SHA `e1c1b53254c18c8c2530320accf4fba0b0fda97738fc92a9a228fe769b8277f0`、属性/種族条件候補2,288、名称グループ候補580、integrity/FK PASS |

C5で`package_candidates`は0件。したがって、M5-Cの未定義中核をM6側で「確定済みのCOREパッケージ」として補完していない。実際の合成試験ではC5の不完全レシピを検出し、別エンジンパッケージの最低必要枠、競合、未選択代替と任意制約を検査した。

### 5テーマ別のsource-era候補件数（privateの集計）

| テーマ | 掲載レシピ参照数 | 候補MAIN/EXカード種類ペア | 低コスト候補 | 既存C2ルート | 所属未解決のルートカード |
|---|---:|---:|---:|---:|---:|
| イビルツイン | 1 | 34 | 0 | 1 | 0 |
| 軍貫 | 1 | 34 | 1 | 0 | 0 |
| 海晶乙女 | 0 | 0 | 0 | 0 | 0 |
| ブラック・マジシャン | 0 | 0 | 0 | 0 | 0 |
| スピードロイド | 0 | 0 | 0 | 2 | 5 |

ここでの「34」は**枚数でなく、MAIN/EX所属を含む候補カードの種類ペア数**。軍貫はC1の掲載レシピ＋C3の代替候補を合算ではなく集合で集計。イビルツインの記事はMAIN40記載に対する可視39枚の不整合を維持。海晶乙女、ブラック・マジシャンに根拠のない完成レシピを作っていない。スピードロイドのC2ルートに出現する5カードはZONEを推定して固定パーツへ入れず、`route_only_card_ids`に保持。

非公開の独立ソース検査ファイル `MD_M6_2_PRIVATE_SOURCE_INSPECTION_20261111.json`、3,101バイト、SHA256 `90fa9f24b2080c965cf593bc725663a91448d0213b430939cc95de8fe374f40d`。Drive ID `1vxV6aKjRIYFpmlr4IOQPWSKShDcTR4Qm`。公開Gitには実カードの候補個票/所持内訳を追加しない。Drive新規アップロード後、別要求で読戻し・同じファイル名/容量/SHAを照合した。

**検証境界**：非公開ソースの監査はGitHubに置いたM6-2コードをそのまま実private環境で呼び出した結果ではなく、ソース独立検査。GitHubの合成回帰は実装コードの動作検証。両者を合算してM6-6の統合受入済みと称さない。

## 回帰・次工程

合成テストは`test_m6_2.py`と`test_m6_2_m5_inputs.py`で、記事枚数欠損、数量差、所持UNKNOWN、source SHA不一致、古いM5-A/B生成元世代、条件共起の誤昇格、出張共有部品の二重計上、競合、EX予算、代替未解決、条件付き風属性ロックを試験する。[GitHub Actions run 42969459477](https://github.com/yukki0113/GPT/actions/runs/42969459477) にて **M6全77件PASS、全体450件・1スキップ・失敗0**を確認（M6-2追加23件＝候補/依存17件＋旧M5索引6件）。最新PRコミット分は別途Actions成功を確認する。

**次はM6-3**。M6-2候補を採用枚数の選択・MAIN40–60/EX0–15構成に変換する。UR0の3条件の判定、M3の禁止制限、所持カード・CPの独立算定はM6-4。M6-2の候補をそのまま合法なレシピとして採用しない。
