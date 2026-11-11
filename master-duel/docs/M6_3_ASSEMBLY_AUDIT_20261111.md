# M6-3 受入監査 — 出典付きレシピの構造的な組立て（2026-11-11）

## 受入判定

**M6-3 PASS：出典付きレシピと既存の低レア代替案から、枚数・カードID・採用根拠が揃った構造的候補を作るコードを実装**。次工程M6-4の最新MD禁止制限、所持カードの必要枚数、生成CP、必須中核妥当性、実戦成立は **未確認**。デッキ構築スレッドでの完成レシピ受入はM6-7。

### 実装

`engine_m6/assemble.py` の `assemble_candidates(request,bundle,pool,max_examined,explicit_edits,selected_packages)`：
- M6-0の`BuildRequest`、SHA/プロファイル一致のM5-C `ThemeKnowledgeBundle` / M6-2 poolを必須入力にする。M5-Cの`recommendation_eligible=false`を消去せず、M6-3が独自に合法・所有・CP保証を発行しない。
- **出典掲載`ARTICLE_RECIPE`と既存の`M5C_VARIANT`を別系統として走査**。MAIN40〜60、EX0〜15、IDごと3枚以下、同カードのMAIN/EX重複、要求/除外カード、カードごとの候補プール根拠、現在のpoolとのSHA一致を検査。
- 元記事の`main_count/extra_count`と可視カード行の合計は**明示編集前に照合**。元記事39/40を後から編集して、元記事自体が正しい40枚だったと偽装することは拒否。明示的なユーザー編集がある場合は必ず`ASSEMBLED`という別出自、編集理由・情報源を保持する。
- 同一カードが元記事と代替案の双方に現れても枚数を加算しない。候補の同一構成はSHAによって重複排除。`max_examined`と`max_variants`で探索上限を制御する。
- 条件付き出張ギミックは、選択が宣言されても自動挿入しない。M6-2の必要部品・選択肢・ロックを確認し、実パッケージを全て組み込む処理はM6-3の現版では`PACKAGE_PARTS_NOT_ASSEMBLED`で保留。
- **コアの成立は`UNKNOWN`**。全カードに出典ごとの採用理由を付け、`STRUCTURAL_CANDIDATE_ONLY`と`requested_mode_evaluation=PENDING_M6_4`を残す。 `LOW_RARITY_CORE`、`STRICT_NO_UR`、所有済みUR・生成CP、禁止/制限のPASSはこの工程では算定しない。

### 合成回帰

`engine_m6/tests/test_m6_3.py` の**18件**：2案抽出・安定ID・掲載39/40不一致・レシピ不足・元SHA異常・別プロフィール・STALEレシピ/代替候補・指定カードの除外・根拠なし追加・編集40枚の別出自・探索上限・同一構成重複・EX上限0・パッケージ自動挿入禁止・入力非破壊を検証。

[GitHub Actions run 42973911955](https://github.com/yukki0113/GPT/actions/runs/42973911955)：**M6 95件PASS、全体468件・1スキップ・失敗0**（実例を含まない公開合成テスト）。最終コミット/PRのCIは別途確認する。

## private実データ：独立ソース再検証

M6-3新モジュールをそのままprivate実カードデータへ実行した試験ではなく、**SHAピン済み現行正本とC5 source-eraレシピを別のread-only検証プログラムで照合した証跡**。コードの合成回帰と混同してM6-6統合受入済みとは扱わない。

| 入力 | 照合 |
|---|---|
| Drive正本HEAD | Generation5、raw SHA `0799c1d946bf31f10fd92187e933ebaa17caa4aea16994a60c72d55f7e4949d9`、検証前後同一 |
| 現行SQLite | ZIP SHA `f8bc126ebf9335e8aa3cd9ffaaeceb2afd7bb8d944d13bfd5d5ba389b0b0f573`、内部SQLite SHA `662f905fe9fe3f6b41d26c33e8780bd920743e6348903cd0d53bcb99ce77a289`、登録13,948種類 |
| C5知識 | ZIP SHA `f3a5c4798fb3ce8b4c78e9c9ea2a704ad34dfb5fb5eb70aea1c5c76c10d09e53`、manifest SHA `fddc571438e6692a826f99ada813e794027ae34ebc3059ddd1d771169a57b3db`、全3メンバー一致 |

| テーマ・ソース | 可視MAIN | 可視EX | 結果 |
|---|---:|---:|---|
| 軍貫 掲載レシピ | 40 | 15 | **STRUCTURAL_CANDIDATE_ONLY** |
| 軍貫 旧C3 UR採用0の仮説版 | 40 | 7 | **STRUCTURAL_CANDIDATE_ONLY** |
| イビルツイン 掲載レシピ | 39（記事宣言40） | 15 | **BLOCKED**：宣言合計不一致／MAIN不足 |

軍貫2案は現行マスターに各カードIDが存在し、各カードのレアリティおよび枚数構造が一致。軍貫に`GAME_TESTED`の展開ルートはなく、必須中核は`UNKNOWN`。**この状態で実用・正式合法・手持ちだけで組める・追加CP0とは断定しない。**

### 非公開Drive新規保存と独立読戻し

`GPT/MasterDuel/DB/`へ以下3ファイルを新規追加。保存後に**別要求で再取得し、rawバイトSHAをmanifestと照合**。source-eraの実カードレシピはpublic Gitに出さない。

| ファイル | 容量 | SHA256 | Drive ID |
|---|---:|---|---|
| `MD_M6_3_PRIVATE_STRUCTURAL_SOURCE_REPLAY_20261111.json` | 1,485 | `e3463e778e4b602191fc00d4db9a216150c98654a54d4d6a34f9d82ad17c9ccc` | `19uYEj0IwZvTR7k3YwT4hS42wb35s7toG` |
| `MD_M6_3_PRIVATE_STRUCTURAL_CANDIDATES_20261111.json` | 18,188 | `c8417d4155f32914f0b71451dfbdf9d2902453651e0173e3e81667a02adfcb0f` | `1Mf-Kb4Lx3lPomm9azlsU8-IcaFIPklvW` |
| `MD_M6_3_PRIVATE_SOURCE_MANIFEST_20261111.json` | 466 | `b393b1fca0fe737b7d56d518ee38855f7a6ff637cb910fc627ed1846e123459e` | `1c21oTzFUgohfAb8aAH_jBPzblt4a0xP6` |

## 限界・次工程

1. M5-Cはすべて`recommendation_eligible=false`であり、M6-3ではこの値を不当に解除しない。
2. M5-A/B索引は旧Generation3ソースに依存するため、未再検証の出張を自動採用しない。M6-3ではあくまで**構造的な元レシピ・出典付き低コスト代替**の生成が成功した段階。
3. 不足1枚のイビルツインや、完全レシピ未取得の海晶乙女・ブラック・マジシャンは、出典なしのカードで埋めない。
4. **次のM6-4**：Generation5の全所持preflight、施行日つきM3候補/確認済み規制、UR0の3つの判定、レア別30CPと生成可否UNKNOWNを分け、M6-3の2案を評価する。
