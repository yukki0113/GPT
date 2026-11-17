# M6-8 融合EX候補・素材机上審査・オフライン正式実行（2026-11-17）

## 適用範囲と目的

構築スレッドごとに別の比較器を再実装しない。GitHub `main` の `engine_m6.recompose.recompose_portfolio` を共通の正式実行入口とする。実行環境がGitHubホストに直接接続できない場合も、ソースをバージョン固定で配布し、入力が揃えば実行できるようにする。

この手順は**デッキ生成機能・入力の接続方法**を整えるものであり、融合ルートのゲーム内成立、対戦での勝率、EX全15枠の価値を証明するものではない。

## 1. 実行環境の標準化（ネットワーク制限環境）

- 正本はGitHub `yukki0113/GPT` の特定コミット。毎回最新mainを確認し、使用コミットを固定する。
- `.github/workflows/master-duel-runtime-bundle.yml` が `master-duel/engine_m5/` と `engine_m6/` の**正式Python実装一式**をZIP化してActions artifactとして公開する。合成テストに合格した版のみパッケージ化する。非公開DB、所持、評価ポリシー、実カードの効果文は含めない。
- GitHub Actionsの該当runから `md-m68-runtime-<commit>` artifactを取得し、外側のActions ZIPから `md-m68-runtime.zip` を取り出し、作業ディレクトリに展開する。`GIT_COMMIT_SHA.txt` および `FILE_SHA256SUMS.txt` の検証を必須とする。GitHubコネクタのartifact download機能を利用できる場合はそちらを優先し、ブラウザや`git clone`に固執しない。
- `engine_m6` を単一ファイルとしてコピーしない。相対import先 `engine_m5` も含む同一スナップショットを使う。依存不足の際は実行環境問題として報告する。
- ZIPを展開したディレクトリで `python -m unittest discover -s engine_m6/tests -p 'test_*.py' -q` を実行し、回帰が通ってからプライベート入力を使用する。
- ZIPの取得ができない環境では「GitHubのソースを読めた」ことを「正式モジュールを実行できる」と言い換えない。代替の独自比較器を作らず、具体的な転送不能要因を記録する。

## 2. M6-5A：融合EX候補の検索

`discovery.search_cards(section="EXTRA")` は、ランク・リンク・リンク本文に加え、**レベルを持ち、素材列挙の＋記号と融合召喚の本文根拠を持つ融合候補**を検索する。MAINの「融合召喚を行う」だけではEXと判定しない。

`theme_terms` または `exact_card_ids` を使い、DBと一致するSHAを必ず渡す。出力はあくまで `UNVERIFIED_CANDIDATE` であり、融合モンスターであること、EXへ採用可能であることをゲーム内確認したわけではない。曖昧・複雑な融合本文は手動レビューする。

## 3. M6-5B：融合素材の机上照合

`material_screen.screen_extra_materials` は、カード日本語本文の**1行目にある、単純な「素材A＋素材B」等の列挙**をNFKC正規化して取得する。追加記述（「以上」、選択条件、除外条件など）を伴う複雑な素材要件は従来どおり `REQUIRES_REVIEW`。

単純な融合素材については、既存の `board_capabilities` の一要素として次を渡す。

```json
{
  "kind": "FUSION_MATERIALS",
  "level": null,
  "count": 2,
  "distinct_names": false,
  "material_labels": ["「架空A」モンスター", "「架空B」モンスター"],
  "evidence_ids": ["PRIVATE-ROUTE:SOURCE-ANCHORED-EXAMPLE"],
  "verification": "HYPOTHESIS"
}
```

`material_labels` は本文からの**完全一致の素材カテゴリ名**であり、単なるカードIDや「ファーニマルがいるはず」といった推定値ではない。上記は架空カードによる契約例。実カードの確認済み素材分類と、それを満たせると考える根拠をprivate入力として保持する。**素材を提示できない場合は `REQUIRES_REVIEW` のまま。**

ラベルと素材数が一致した場合のみ `POSSIBLE_ON_PAPER`。これは**ゲーム内で同時に素材を揃えられる／融合カードで実際に召喚できる**という認定ではない。召喚制限、効果の発動時点、融合魔法、墓地使用可否などは別レビュー。

## 4. M6-8正式再構築の入力束と実行

`engine_m6.runtime_recompose` は**新たな採点器・比較器ではなく**、既存 `recompose_portfolio` を正式な入力で呼ぶオフラインCLI。入力はprivate JSONであり、公開リポジトリへ保存しない。

必要なトップレベルキー（**すべて必須**）：

```text
request
teacher_candidate
discovery_results
annotations
material_screen
engine_packages
decision_policy
regulation_policy
```

`discovery_results` はM6-5A、`material_screen` はM6-5Bの正式出力を渡す。自作のカード一覧やEXの候補リストをそのまま正式出力と偽装しない。`decision_policy` は`build_policy_v2.validate_build_policy_v2`の7項目スキーマに従い、評価値・コピー別根拠・出典・カードIDを含む。`regulation_policy` は承認済みMD規制基準版を使用する。

```bash
cd <runtime-unpacked-root>
python -m engine_m6.runtime_recompose \
  --input /private/m68_inputs.json \
  --expected-policy-sha256 <selection-before-precommitted-canonical-policy-sha256> \
  --output /private/m68_official_result.json
```

CLIは**元ポリシーSHAの不一致、正式v2スキーマの不一致、M6-5A/B入力不足、DB/SHA不一致をエラーとして停止**する。使用した評価は事前固定し、選定結果を見て点数を修正しない。結果JSONはprivateでのみ保管。画面上は成功/失敗と必要最小限の監査要約を出す。

## 5. デストーイ（2026-11-17）の未解消事項

- `DESTOY_M68_PRESELECTION_POLICY_20261117.json` の元SHA `4a5cad3c998dd5e5db348539a4f5d3a278b2540133e9c1cd48106130b1506889` は**元形式に対する固定記録として保持する**。元形式に `candidates` 等の余剰キーがあり、正式v2形式とは異なるため、そのSHAのまま実行したと称しない。
- 形式変換版が存在しても、**別ポリシー・別SHA・別試験**として明示する。カード別評価や1/2/3枚目の値を無言で変更しない。元JSONと変換版のフィールド対応、値の保存、欠落根拠を監査する。元JSONを直接確認できない環境では変換を完成扱いしない。
- M6-5Aの融合候補検索とM6-5Bの融合素材審査が追加されたからといって、デストーイのEX15枚の適合性・ヴェルテ・アナコンダの発動後制約が自動的に証明されるわけではない。
- 現時点で公開CIが保証するのは**架空カードでの機械的な回帰**。Gen6での正式デストーイ実行は、private最新HEADと完全な入力束を接続し、上記CLIを通したときに初めて判定できる。

## 6. 構築スレッド向け運用指示

1. mainの現行WORKFLOWとM6-8仕様を再読し、利用したコミットを固定する。
2. GitHub実装のZIPを取得して合成テストを実行する。実行できなければ**具体的な障害のみ**報告し、ローカル代替比較器を作らない。
3. private DBをSHA照合し、M6-5A検索・M6-5B机上審査の正式入力を作る。融合素材は実際の効果本文に根拠のある場合のみ `POSSIBLE_ON_PAPER`。
4. 固定済みポリシーは不変保管し、正式v2に変換する場合は別SHA・別試験と明記する。
5. CLIで`recompose_portfolio`を正式実行し、既存デストーイ40/15と差分を比較する。ここで初めて「正式M6-8再現」を判定する。結果により採点値を後出し変更しない。
6. 完成レシピには戦略サマリー（勝ち筋、主な展開、補助、代替）のみ簡潔に添える。全カードの採用理由や全ルート証明は通常必須でない。
