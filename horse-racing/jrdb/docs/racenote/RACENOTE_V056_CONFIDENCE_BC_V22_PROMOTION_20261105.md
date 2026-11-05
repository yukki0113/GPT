# RaceNote v0.5.6 Confidence B/C — Shadow v2.2 研究の採用範囲と正式定義（2026-11-05訂正）

Status: **CURRENT / CONFIDENCE DEFINITIONS RESTORED**  
対象: 新規・未Freezeのv0.5.6 BTDAY / FORWARD。予想印、既存Freeze、v0.5.5再現系には遡及しない。

## 1. 初回昇格判断の訂正

初回コミット `f2d5fe440b460ce23b0cb3de7af5674f6ff7ece4` は、Shadow v2.2の「◎が3着内に残る軸の信頼性」を正式ConfidenceのB/C定義に置き換えた。この**定義変更を撤回**する。

Shadow v2.2の研究成果は、レースごとの証拠照合・印5頭の比較・不確実性の説明を丁寧に行う**補助レビュー手法**として採用する。ShadowのB/Cラベルを正式Confidenceへそのままコピーしない。

## 2. 正式なA/B/C/Z

- **A — 勝ち切りを積極支持**：◎を勝ち馬として強く支持できる。単に「◎が最有力」というだけでなく、現在条件で再現性のある勝ち筋と、他の勝利候補への十分な比較優位がある。従来のA基準を維持する。
- **B — ◎最有力だが勝ち負けできる他馬もいる**：◎が勝つ可能性を最も高いと判断している一方、○や他の候補にも現実的な勝利経路がある。勝ち馬としての◎の比較優位は説明できるが、Aほど明確ではない。
- **C — 印5頭間で勝利の優劣がつけにくい**：最終5頭の勝利候補について、◎を最上位とする比較根拠が拮抗・非決定的で、勝ち馬の序列への確信が低い。◎を1頭選んだことと、◎を強く支持できることは別。
- **Z — 特殊対象**：従来の新馬戦・障害戦等の別枠。A/B/Cの上下関係に置かない。従来の適用対象を維持する。

**重要：Cに「◎が4着以下になる具体的な懸念・根拠」を必須条件として要求しない。** ◎が3着内に残る見込みが高くても、勝ち馬としての5頭間序列を確信できない場合はCでよい。Bも「◎が3着内の軸に適する」という条件で定義しない。

A/B/Cの目標件数や比率、固定スコアや機械的な件数調整は禁止する。公開上の見た目を理由にCを増やさない一方、拮抗しているレースを根拠なくBに寄せない。

## 3. PredictionとConfidenceの工程・責務

1. LLMが全出走馬を比較して、通常の展開で有力な**ordinary five**を構成する。
2. ordinary fiveから、勝ち馬として最有力の◎と、次に重要な勝ち筋の○を選ぶ。
3. 外部Challengerを最大1頭検討する。既存契約どおり、十分な根拠がある場合のみ◎○以外の下位ordinary候補と入れ替える。KEEPが原則。
4. 最終印 ◎○▲△△ とDecision Coreを **Prediction Freeze** する。
5. その後の独立Confidence Reviewで、既に固定した◎が他の勝利候補を上回る確信度をA/B/C/Zで著述し **Confidence Freeze** する。

◎や最終5頭の選別に重大な疑義があるなら、Prediction Freeze**前**に序列やChallengerとの比較を見直す。Confidence Reviewで新たに問題が見つかっても、既に凍結した◎・印を黙って変更せず、品質問題として監査する。Confidenceを使って既存Predictionを後から改変しない。

## 4. Shadow v2.2から利用する観点（補助レビューのみ）

- ◎○▲△△の5頭について、実走履歴、同条件再現性、脚質、展開、相手関係、リスクと不確実性を具体的に比較する。
- 「○が◎に勝つ」ことと「◎が4着以下になる」ことを混同しない。ただし後者をCの成立要件にはしない。
- 初出走・既走0では入力欠損と実走履歴なしを区別し、事前IDM・KYI・CYB・調教等の複数の独立した材料を印5頭と比較する。初出走だけで機械的にCへ落とさない。
- B/Cいずれも、◎を最上位とする根拠、ほかの勝利候補の根拠、優劣の明確さ／曖昧さをレース固有の証拠で言語化する。

第1期BTDAY-0152〜0161（309R）はv2設計に用いた標本、第2期BTDAY-0162〜0171（336R）は事前固定したv2.2の研究検証標本である。両期のShadow判定・原票・結果は不変。Shadowの着内軸判定やROIを正式Confidenceの意味へ転用しない。

## 5. 実装・Freeze境界

- BTDAY/FORWARDに同じLLM著述規則を用いる。Pythonによる印・Confidenceの自動格付けは行わない。
- 既存の `confidence` と `confidence_review`（`winning_case`, `primary_rival`, `relative_advantage`, `main_defeat_scenario`, `risk_assessment`, `final_grade_reason`）の構造を維持する。レビューの主語は「◎が勝つか／ほかの候補に勝つか」である。
- Confidence Freeze前の結果・払戻・対象当日市場は参照禁止。既存Prediction/ConfidenceのSHAを変えない。A/Zと従来v0.5.5運用を変更しない。
- 構造ValidatorのPASSは競馬的な意味論のPASSではない。Freeze前に判定理由の質を確認する。
- 馬券収益の研究はConfidenceから独立させ、次段階はAの購入価値・見送り判断を優先する。

## 原典
- `docs/racenote/FORECAST_HUMAN_CONTEXT_READER_v0_5_5_CANDIDATE.md`：ordinary five・Challenger・A/B/C。
- `docs/racenote/RACENOTE_V056_MIGRATION_IMPLEMENTATION_CONTRACT_20261030.md`：v0.5.6の独立Confidenceと二段階Freeze。
- 研究資料：`research/racenote-shadow-v2-0162-0171-pre-result-20261105`（Shadow v2.2。正式Confidenceの定義とは別）。
