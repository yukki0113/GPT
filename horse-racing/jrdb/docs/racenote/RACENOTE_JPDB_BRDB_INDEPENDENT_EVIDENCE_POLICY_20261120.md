# RaceNote × JPDB × BRDB — 独立Evidence拡張の基本設計・開発方針（2026-11-20）

**Status: POLICY ADOPTED / INTEGRATION DESIGN / NOT PRODUCTION APPROVED**

## 1. 開発の共通目的

RaceNoteの現在の予想は過去走・RaceReviewに大きく依存し、既走実績のある馬や、市場で高く評価されやすい馬に判断が寄りやすい。過去走のない新馬戦は判断材料不足によりConfidence Zに寄り、実質的に予想が難しい。

**JPDB（騎手）とBRDB（血統）の共通目的は、過去走だけでは見えない条件適性・潜在的な可能性を、実際に確認できる事前根拠としてRaceNoteへ渡し、全馬比較に別視点を追加すること。**

DBは◎○▲、Confidence、勝率を決定しない。JPDB/BRDBが提供するのは事実、相対的な傾向、根拠ID、比較対象、標本数、不確実性、データ取得時点。どの根拠をどう読むか、既存評価を支持・修正・覆すかはRaceNoteが判断する。

馬質と騎手能力の完全な因果分離、血統適性の完璧な統計的証明を、情報提供の研究を始める絶対条件としない。ただし未認証の能力や適性を確定値として本番へ送らない。**データ品質を妥協せず、学術上の未解決課題が実用研究を不必要に停止させない**。

## 2. 想定ユースケースと評価軸

### 既走馬

- 既存の過去走評価と独立した騎手条件実績・血統条件傾向を提示できるか。
- 過去走で低く評価した馬を、妥当な根拠で再検討できたか。逆に強い実績馬を支持する判断も正当。
- 人気薄への誘導は目的ではない。既存評価と同一内容の二重加点・人気/馬質バイアスの増幅は避ける。

### 新馬戦・実績不足馬

- 馬自身の過去走がないことを、能力・適性がない証拠にしない。
- BRDBの父・母父・配合・近親の条件実績、JPDBの騎手条件別実績、既存RaceNoteの調教・厩舎等、利用可能な事前根拠で全馬比較できるかを研究。
- 「新馬戦が得意な騎手」「デビュー初戦の血統傾向」は有望な*研究対象*だが、JPDBで新馬戦識別子が整備・受入済みとはみなさない。BRDBの未実装・as-of未認証の根拠も使えるものとして捏造しない。
- 既存Confidence Zの分類や二段階Freezeを直ちに変更しない。根拠の充実によってZ以外に分類可能かは独立した検証・変更承認が必要。

## 3. DB別の責務

- **JPDB**: 予定騎手は対象日のPACI/KYI、歴史騎乗はSEDの実騎乗者。場・芝ダ・距離・Course Masterの物理条件・期間別の記述的実績を生成。本人の他条件、同条件の他騎手との比較に標本数・馬質交絡・機会差を付与。P3の馬期待値・最終オッズ・騎手変更研究は感度分析として活用するが、純粋な騎手能力の確定値としない。
- **BRDB**: 血統の父・母父・系統組合せ・兄姉や近親・cross等の利用可能な根拠を同一対象レースの全馬へ提供。未実装はNOT_IMPLEMENTED、時点未認証はAS_OF_UNVERIFIED、小母数はLOW_SAMPLE等で区別。血統成績の交絡・根拠の重複を隠さない。
- **RaceNote**: DBの内部Parquetや研究スコアを直読しない。承認済みReader-facing evidenceを全馬比較で読み、支持・反証・矛盾・重複を検討。固定加点や一項目による自動印生成はしない。採用した根拠IDをDecision Traceへ紐づける。

## 4. 新ロードマップ

1. **R1 事実**: JPDB条件プロフィールとBRDB統合血統レビューについて、現行Reader/既存実装を再利用し全馬coverageと対象条件の正確さを検証。
2. **R2 解釈**: 騎手の相対的な条件適性、血統の同条件傾向、小母数、期間別の矛盾、複数条件の重複、対象馬の実績不足を安全に表現。
3. **R3 共通契約**: race_key_raw×horse_no、JPDB予定騎手コード、BRDB horse_id、target_date、as-of、source SHA、coverage、evidence_id、redundancy_groupを持つ独立sidecar。既存のv0.5.6 KYI allowlistやReader sealは変更しない。
4. **R4 Shadow**: 既走馬と新馬戦を**別コホート**として、現行予想を変更せず証拠の取得・矛盾・既存情報との重複を監査。
5. **R5 A/B**: 事前にレース・評価指標・論理版を固定し、JPDB/BRDBなし／ありで予想判断を別々にFreeze。結果は両系統のFreeze後に開く。既存評価からの再検討数、新馬戦の全頭比較可能性、判断の妥当性、重複加点・過信、的中・3着内・不確実性を比較。約50Rは初期読解監査単位であり、性能効果を統計的に認証するための十分数とはみなさない。
6. **R6 採否**: 実レースのblind/forward検証、source・時点・identity・coverage・禁止情報遮断・解釈品質の受入後、対象RaceNote版・Reader差込箇所・Decision Traceの契約を明示して別承認する。

## 5. 不変条件

- 対象日結果、払戻、確定オッズ・最終人気、事後レビューをpre-Freezeへ混入させない。
- 過去SEDの翌日可用仮定と、実際の過去配信版の時点証明は別。KYI過去年次FINAL proxy・2026保存PACI・BRDB歴史資料の時点未認証を本番可用として扱わない。
- 欠測・小母数を「不得意」「適性なし」としない。馬質・騎乗機会、血統と厩舎・馬の選抜がもたらす交絡を明記する。
- JPDB/BRDBで同一集団を重複観測する条件を独立票として足し合わせない。
- この方針書は**設計目的と研究ロードマップ**を確定する。既存v0.5.6 Prediction/Confidence二段階Freeze、Confidence Zの正式定義、Gen0.3未有効化状態、PWA/CURRENT、既存凍結済み予想を変更・承認するものではない。

## 6. 既存資産への参照

- JPDB基本再設計: `../JPDB_RACENOTE_JOCKEY_PROFILE_REDESIGN_20261120.md`
- JPDBの能力残差感度: `../JPDB_P3_KYI_PROXY_SENSITIVITY_20261120.md`
- BRDB統合血統レビュー候補: `../../../brdb/docs/BRDB_INTEGRATED_BLOOD_REVIEW_CONTRACT_v0_2_CANDIDATE.md`
- RaceNote既存血統導入設計: `RACENOTE_PEDIGREE_ENRICHMENT_DESIGN_v0_1.md`
- 現行運用: `RACENOTE_V056_FORWARD_PACI_RUNTIME_20261030.md`

**判断原則：JPDB/BRDBは「根拠と不確実性」を渡し、RaceNoteが「今回のレースにおける意味」を判断する。**

## R3研究用共通Evidence契約の受入（2026-11-24）

[共通契約・検証結果](../RACENOTE_R3_INDEPENDENT_EVIDENCE_CONTRACT_20261124.md)。既存R1/R2とBRDB M7受入済み出力を同一PACI・全登録馬で厳密結合する詳細sidecarと、固定表示軸の軽量previewを実装。6R76頭のうち両DBは通常1R18頭、残り5R58頭はBRDB未取得を明示。新馬4R42頭の両DB同時実データ検証は未完了。③④/D4の時点未認証数値は制限付き根拠参照に隔離。R3固定source技術契約PASS、R4 Shadow前に新馬戦BRDB取得・同一全馬結合受入が必要。R4/R5や本番採用・Confidence変更は未承認。

### 2026-11-24 R4 初回Shadow受入追記

[R4初回研究Shadow監査](../RACENOTE_R4_SHADOW_AUDIT_20261124.md) を参照。R3固定6R76頭の根拠監査、現行v056封印済みReader 3R40頭の両コホート照合、新馬戦B5同一4R42頭の専用lane再生成・照合を実測。初回研究Shadow PASS、6R全Reader比較はPARTIAL（6月3R36頭の同版封印Reader未取得）。R5未承認、TRUE_FORWARD・厳密as-of・予測効果・本番昇格は未認証。B5の2026履歴gapとAS_OF_UNVERIFIEDを維持する。
