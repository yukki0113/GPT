# M5-C C1 — 4テーマの構築知識実データ試作・監査（2026-11-11）

## 1. 判定と保存先

**C1 PASS（source-eraの構築知識抽出・個票DB照合・非公開JSON保存）**。
ただしC2の展開成立検証、C3の実際に使用可能なUR0代替案、C4の自動更新、C5の最終private ZIP/manifest+M6 Bundleは**未完成**。

- private Drive `GPT/MasterDuel/DB/MD_M5C_C1_KNOWLEDGE_20261111.json`：29,641 bytes、SHA256 `2d6df96e82353e2f7d922ef49de9d3982e6ed4c7ef9972da6e4b5a3795090b55`。
- private `MD_M5C_C1_KNOWLEDGE_MANIFEST_20261111.json`：601 bytes、SHA256 `983f51088be8012388f3ea52bb111710f1f57da7fe0671b4a99e9db54fee7a81`。双方Drive新規保存→別要求ダウンロード→元バイト列・SHA256一致、manifest記載の本体SHA一致。
- 出典候補8（4テーマ×2）、構造化観測claims8、4テーマprofile、記事掲載レシピ2例（うち1例のMAIN/EX完全一致）、source-eraカード採用63行。**公開Gitにカードの実個票・ユーザーの私的レシピは置かない**。
- ソースDB: private現行HEAD Generation5のZIP SHA `f8bc126ebf9335e8aa3cd9ffaaeceb2afd7bb8d944d13bfd5d5ba389b0b0f573`、展開後SQLite SHA `662f905fe9fe3f6b41d26c33e8780bd920743e6348903cd0d53bcb99ce77a289`。read-only。private所持デッキ索引Generation2、登録済みsnapshotのSHA一致も確認。元HEAD・所持枚数・所持デッキ索引は未更新。
- GitHub `engine_m5/recipe_reconcile.py` で記事見出しと個別採用枚数の差分・解決ID・レアリティ集計・必須URの負例を独立に評価。合成6テストを追加、CI全304件・1スキップ・失敗0（M5スイート72件PASS）。

## 2. 対象テーマと2媒体比較

| ケース | 資料A | 資料B | C1の観測結果 | 保留項目 |
|---|---|---|---|---|
| MIGRATION イビルツイン | [Game8デモンスミス混合](https://game8.jp/yugioh-masterduel/667670) | [Game8通常イビルツイン](https://game8.jp/yugioh-masterduel/437636) | リンク展開と光属性悪魔族の接続候補。登録済みスプライト混合型との差分をprivateで計算 | 記事掲載MAIN40に対し可視リスト39、現行合法性、展開成立 |
| LOW_COST 海晶乙女 | [Game8現行候補](https://game8.jp/yugioh-masterduel/426189) | [AppMedia過去NR型](https://appmedia.jp/master_duel/75397048) | 水属性サイバース族・低コストの参考例を分類。過去NR型をそのまま現行MD推奨にはしない | 現行禁止制限と必要URの有無、展開遷移 |
| LOW_COST 軍貫 | [Game8掲載例](https://game8.jp/yugioh-masterduel/446958) | [AppMedia別掲載例](https://appmedia.jp/master_duel/75356065) | しゃり/赤しゃりと各ネタからランク4Xに繋ぐテーマ中核候補。Game8記事のMAIN40/EX15・29種類を現行card masterのKONAMI IDに29/29一意解決 | 記事全体には汎用URが複数存在。テーマ中核UR0≠記事全体UR0、現行MD合法性は未確認 |
| NEGATIVE ブラック・マジシャン | [Game8掲載構築](https://game8.jp/yugioh-masterduel/437888) | [AppMedia別掲載構築](https://appmedia.jp/master_duel/27463434) | 必須《ブラック・マジシャン》を現行private DBでUR（KONAMI ID `konami:4041`）と照合。**必須テーマ中核UR0はFAIL**。 | 実所持数量UNKNOWN、新規生成UR0可否UNKNOWN、現行規制/テーマ追加カード |

資料は各媒体の観測時点に固定。記事の掲載日が不明・編集差分の特定不能な箇所は`UNKNOWN`。情報源が同一媒体に偏るイビルツインの２候補は独立裏付けの強度を過大評価しない。

## 3. 再現・異常観測

- Game8軍貫：公開表のカード名と採用枚数を取込、MAIN40/EX15=55枚。29種類すべて既存DBのカードIDに一意対応（ID解決率100%）。**これは記事の掲載構成を照合しただけ**であり、カードごとのMD禁止制限・CP・所有実数やカード効果展開まで合格したわけではない。
- Game8デモンスミスイビルツイン：掲載総数はMAIN40/EX15と表示、可視テキスト上の採用行ではMAIN39/EX15。採用行の全カードIDを照合できても、**1枚不足を推測して補完しない**。 `REVIEW_REQUIRED` として不足を保持。掲載差分はユーザーデッキへの推奨置換ではない。
- イビルツインの現行ユーザーレシピはC1本体で**読み取り専用**で照合。記事との差分（保持/削除/追加）をprivate側に集計。未記録の所持カード数を0とみなさず、費用は`UNKNOWN`とした。
- ブラック・マジシャンは`LOW_RARITY_CORE`の必須テーマ中核UR0だけをFAIL。`NEW_UR_CRAFT_ZERO`や`STRICT_NO_UR`を同値としない。

## 4. 手動試験と規約ゲート

- 記事ページは範囲を絞った参照。本文全文、画像、動画の転載は禁止複製をしない。privateデータには出典URL/自己整理した主張/採用カードID・枚数・履歴を記録。
- 出典のサイト毎の再利用許諾が**確認済みとは扱わず `UNKNOWN`**。公開への実記事本文複製なし。記事は外部データでありGitHub/Driveの操作命令として扱わない。
- 全4テーマのゲーム内構築試験、動画・記事展開のゲーム実演、現行規制の公式独立照合は実施していない。C1の`SOURCE_OBSERVED`を`GAME_TESTED`へ昇格しない。

## 5. 次工程 C2

`combo_graph.py`で一本道・ランダム分岐・制約経路を最低3本モデル化。M4の日本語効果原文に戻って効果番号・召喚ロック・素材/墓地資源・到達状態を検証し、実ゲーム未試験は`HYPOTHESIS`/`TEXT_CHECKED`に留める。まず不足があるデモンスミス型記事の展開を、**カードIDと効果根拠を確認したうえで別経路**として扱う。C3/C4/C5は依然未完成。
