# M6-8 EX素材証明不足を採用不可と誤判定する問題の是正（2026-11-18）

## 直接原因

デストーイのM6-8正式再構築で、**サーベル・タイガー**と**シザー・ウルフ**のM6-5B判定がいずれも `grammar=UNPARSED` / `screen=REQUIRES_REVIEW` / `review_reason=ROUTE_EVIDENCE_MISSING` であり、構築側にある素材候補を採点・評価する前に除外されていたとの報告を受けた。

原因はM6-8 `engine_m6/recompose.py` にあり、EX候補とパッケージ必須EX部品について、`screen != POSSIBLE_ON_PAPER` を一律に採用不可扱いとしていたこと。これは**「素材経路の証明がまだない」と「使えないことが分かっている」を混同する**。M6-5Bの厳密な証拠評価を緩める問題ではない。

## 最小変更

- `_extra_material_disposition` を追加し、`POSSIBLE_ON_PAPER` は従来どおり採用候補に、`REQUIRES_REVIEW` かつ**理由が厳密に `ROUTE_EVIDENCE_MISSING`**、さらにゲーム内成立・同時確保・公式MD適法性の各フラグがすべて `False` の場合に限り `PROVISIONAL_ROUTE_UNPROVEN` を返す。
- 限定された未証明ルートは、M6-8のスコアに基づくEX競争選定へ**暫定候補として参加**できる。エンジン必須部品についても同条件で選定可。未認識素材構文を解析できたことにはしない。
- 選定トレースに `material_verification=REQUIRES_REVIEW_ROUTE_EVIDENCE_MISSING` と `provisional_extra_selection=True` を残す。従来の `POSSIBLE_ON_PAPER_NOT_DUEL_VERIFIED` と区別。
- `screen` 欠損、その他の `REQUIRES_REVIEW` 理由（素材不一致、召喚方法不一致、素材構文未解決など）、`gameplay_compatibility_verified` が不正にTrueとなる入力は、従来どおりEXの採用候補から除外。
- 所持制約、新規UR生成制約、禁止制限、採点ポリシーの事前固定、MAIN40/EX15上限等のハードゲートは変更していない。
- **「MAIN/EXに素材が存在すること」は、同時に素材を揃え融合魔法で適正に融合召喚できることの証明ではない。** 本変更は必要な盤面・召喚手段が未検証という事実を保持しつつ、構築候補から不合理に排除しないためのもの。

## 回帰と結果

`engine_m6/tests/test_m6_5c.py` に架空カードだけを使う3件の回帰を追加。
1. `ROUTE_EVIDENCE_MISSING` のEX候補を採点後、暫定採用・専用フラグあり・ゲーム未実証で扱える。
2. 素材不一致・召喚方法不一致・単なるUNPARSEDなどは引き続き除外。
3. 必須エンジンのEXもルート証拠不足だけで一律BLOCKしない。

GitHub main コミット：`bec59003d6bec5445dc6735b988fc5c120d5d93c`（本体）、`8860b831b4998f1410227885818c376c9a9c3afe`（合成回帰）。

GitHub Actions [Python regression 44215129937](https://github.com/yukki0113/GPT/actions/runs/44215129937) **SUCCESS**：engine_m6 351 tests, 0 skipped PASS、TOTAL 729 tests, 1 skipped PASS。 [M6-8 runtime bundle 44215129980](https://github.com/yukki0113/GPT/actions/runs/44215129980) **SUCCESS**。

## 未実施・引渡し

これは検索漏れではなく**採用ゲート誤分類の修正**であり、デストーイの非公開55候補とGen9入力束を再実行したものではない。両カードの採用を保証せず、競争得点・EX枠・UR・規制・効果制約で未採用になる余地は残る。次は構築スレッドで新しいコミットを使って同じ事前固定採点ポリシーにより再実行し、両カードの `competitive_decisions`／`competitive_candidate_comparisons` に採否・トレースが残ることを確認する。デッキの実演・召喚ルート全証明の作業は本修正の必須条件としない。

公開リポジトリにはデストーイの個別カードID、実所持、私用レシピ、元の日本語効果テキストを保存せず、監査は概念・集計のみを保持する。Gen9本番DB・HEAD・禁止制限は変更しない。
