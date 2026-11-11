# M5-C C3 — 低コスト代替候補・失われる能力の比較監査（2026-11-11）

## 判定と境界

**C3 PASS（UR0構成の候補比較・差分・損失・未検証状態の保存）**。軍貫のsource-era掲載レシピ（MAIN40・EX15）を起点に、privateカードマスターのレアリティ・効果原文と照合し、**UR0の候補MAIN40・EX7**を作成した。これはM6の完成合法デッキやゲーム実演済みの構築ではなく、**`REVIEW_REQUIRED` の候補**。禁止制限/所有数/SR以下の生成可能性を未検証のまま確定しない。

- C1の元記事：<https://game8.jp/yugioh-masterduel/446958>。参照時点と現行規制を区別。元C2 knowledge SHA256: `e9313cdd0adbd7152829b195a742f9e06554e309feda14c8fe04ed7f246d080f`。
- 参照したprivate現行カードマスターZIP SHA: `f8bc126ebf9335e8aa3cd9ffaaeceb2afd7bb8d944d13bfd5d5ba389b0b0f573`。SQLite SHA: `662f905fe9fe3f6b41d26c33e8780bd920743e6348903cd0d53bcb99ce77a289`。HEAD Generation5。ZIP/SQLite生バイトを再計算し、SHA一致したprivate DBを**read-only**使用。MDレアリティ・カード本文の検証はprivateのみ、公開GitHubには個別レシピを含めない。

## 元構築と代替の比較

| 指標 | 元の掲載例 | C3候補 |
|---|---:|---:|
| MAIN | 40 | **40** |
| EX | 15 | **7** |
| MAIN UR | 13 | **0** |
| EX UR | 7 | **0** |
| 合計UR | 20 | **0** |
| 合計枚数 | 55 | **47** |
| 状態 | `SOURCE_ROWS_RECONCILED` | `REVIEW_REQUIRED` |

- 変更前後で**33枚を維持、22枚を削除、14枚を追加**。削除22枚はUR20枚＋低レアの依存パーツ2枚。
- UR7枚を除いたEXには、軍貫のR/SRエクシーズ3種類などが残る。一方、アーゼウス、未来龍皇ホープ、各種希望皇ホープ系のUR到達点は失われる。
- 希望皇ホープ・ダブル（SR）とダブル・アップ・チャンス（N）は、原案の《希望皇ホープ》URを外した後の専用パーツとして**理由付きで別途除外**。これは現時点の案における合理的なパーツ整理であり、あらゆる他構築で利用不能という意味ではない。

### SR以下の追加候補（private DBで実在/レアリティ/効果原文照合）

| カード | 追加枚数 | レア | 相互作用の扱い |
|---|---:|---|---|
| おすすめ軍貫握り | 3 | SR | 「しゃり」提示と相手選択が必要な軍貫サポート。安定サーチとは未確定 |
| 月の書 | 3 | R | 表側モンスターの裏側化。UR手札誘発の代替ではない |
| 禁じられた聖杯 | 3 | R | 場の表側モンスターに作用する効果無効候補 |
| 強制脱出装置 | 3 | R | 場のモンスターのバウンス候補。手札効果は抑制できない |
| サイクロン | 2 | R | 魔法罠の単体除去 |
| **合計** | **14** | | 全件 `HYPOTHESIS` |

※この表は開発上の採用候補の要約であり、効果の裁定やカード強度を保証しない。各カードの正本ID・効果SHA・採用理由はprivate C3 variant内に保持。

### 成立条件・残る経路と失う経路

- しゃり・赤しゃり・うに・いくら・しらうお、3種類の軍貫EXなどを**候補中核として保持**。この集合のレアリティについてはSR以下を確認。ただしC1時点で個別カードの`essentiality`はUNKNOWNであり、「これらが必須の証明済み中核」とは呼ばない。
- C2の既存3ルートはイビルツインとスピードロイドの実例。**軍貫のC2検証済みルートは0件**のため、失った/残った展開の個別ゲーム成立は`UNKNOWN_NO_SUSHIP_C2_ROUTE`。未検証の妨害数・成功率を捏造しない。
- `STRICT_NO_UR`: **UR採用0を構成上PASS**。`NEW_UR_CRAFT_ZERO`: **本案はUR自体が0のためUR新規生成0を構成上PASS**。ただし SR/R/N必要枚数の所持・生成可否・CP残高・現行禁止制限は全て別ゲート。M2所持全件preflightを未実施であり、追加14枚の所持を断定しない。
- ブラック・マジシャンの必須中核UR0は依然FAIL。海晶乙女はC1に完全なsource-era MAIN/EX一覧がないため「UR0完成構築」を捏造しない。イビルツインのデモンスミス掲載例はMAIN40表示/可視39の矛盾が残り、C3への直接引き継ぎを保留。

## 公開実装・回帰

- `engine_m5/low_cost_variant.py`: `assess_low_cost_variant`はC0知識スキーマ検証→C1元記事全量枚数照合→PIN済みprivateマスターのカードID/MDレア照合→明示的な削除と低レア追加→MAIN/EX枠・カード上限とUR0判定→残存/喪失/未確認ルート・費用の区別を実施。
- 追加・低レア依存パーツの削除には理由と`HYPOTHESIS/TEXT_CHECKED/REVIEWED`の検証状態が必要。`GAME_TESTED`への自動昇格は拒否。source SQLite SHAは必須の入力。元レシピの不一致を勝手に埋めない。
- 合成回帰で枚数不一致、CARD ID不明、UR追加の拒否、コピー上限、根拠不足、所有UNKNOWN時の生成可否と必須中核UR負例を検証。
- 本C3は現行MDの合法性/禁止制限/生成可否とSR/R/N実所持を保証しない。`REVIEW_REQUIRED`の成果物をM6の確定結果として使用しない。

## private Drive保存・読み戻し

private `GPT/MasterDuel/DB/` に追加、アップロード応答とは**別API要求で独立再ダウンロード**して3件とも保存前の生バイト・SHA一致、manifest記載の2ファイルSHAとの照合もPASS。

| ファイル | 容量 | SHA256 |
|---|---:|---|
| `MD_M5C_C3_KNOWLEDGE_20261111.json` | 58,003 | `8812f23d07b616168de9326d6c991e8f422aa68adfddb93b4a9b9414415a9be0` |
| `MD_M5C_C3_VARIANT_20261111.json` | 15,424 | `eec847b4ee58af08ac39580dcdb1d9532e2691e76a3288ff9c67c00f40c9f202` |
| `MD_M5C_C3_KNOWLEDGE_MANIFEST_20261111.json` | 805 | `5a3038653dee7ab4bb12f5822101d9d0e9f45e78a0e1d6cf8156d32bf13410bd` |

**Drive IDs**: knowledge `1HR76qZSEwrtbsiXqHwMV_39tF4WMuz2C`, variant `1RlG9J1eSYwWtD4kfJoJ7DlrRtIALQ-A5`, manifest `1ER1iNcUr8SoZYo0mAL_OYvvulay7muKk`。C2知識は変更せず、C3版へ新規追加。実所持デッキ索引と本番HEADへの書き込みなし。

## 次のC4

source revision・カード本文SHA・BANLIST施行日の差分をキャッシュキーへ反映し、影響するclaim/recipe/route/low-cost候補だけSTALE化する。過去の版を残し、再調査の範囲と実行回数を制御する。C5のM6 Bundle APIは別工程。
