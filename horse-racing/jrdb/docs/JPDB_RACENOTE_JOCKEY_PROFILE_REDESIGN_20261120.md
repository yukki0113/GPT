# JPDB → RaceNote 騎手条件プロファイル再設計 v0.1（2026-11-20）

Status: DESIGN PROPOSAL / SIDECAR NOT IMPLEMENTED / PRODUCTION NOT APPROVED.

## 1. 目的・方針

最終目的は、RaceNoteの各出走馬に「今回の条件について予定騎手にどのような履歴傾向があるか」を、出典・母数・不確実性つきで渡すこと。騎手の真の因果的能力値を証明することではない。

開発順を「P3能力推定の完成→P4接続」から、「P1/P2の条件実績→限定的Profile Builder→RaceNote外部sidecar Shadow→同一レースA/B評価→本番採否ゲート」へ変更する。P3の因果能力推定は並行研究として保存し、sidecar作成の必須条件としない。

## 2. 継承する成果・保留

- P1/P1.2: 2023年以降のSED実騎乗者別集計。3暦年/365日/90日。歴史SED翌日可用は仮定でありstrict as-of認証ではない。
- P2 Raw: venue、surface×exact distance、class/grade raw、going raw、course raw code。raw codeを物理コースとして扱わない。
- P2 physical: BAC→Course Masterによる時点有効なコースと形状の同定。属性はPARTIAL、NULL補完禁止、2023年以降の保守的epochのみ証拠あり。
- P3 market/horse: 最終オッズ補正は回顧的分析。KYI馬質proxy追加により騎手別残差の年跨ぎ相関が大きく変化。純粋な馬質と騎手能力の因果分離は未認証。
- P3 same-horse switch: 選抜過程の違いを示す記述的比較であり乗替り効果ではない。
- RaceNote: 共通F07「騎手・厩舎」。Gen0.3 candidateのDATA_TREND/JOCKEY_TRENDは研究候補。現行日次v0.5.6のPACI→Reader→二段階Freezeとは契約が別。Gen0.3は未有効化。既存v0.5.6 KYI supplemental bundleは厳格なallowlistを持つ。

## 3. リリース単位

### R0: 語彙・安全規則

OBSERVED=過去の条件別事実。CONTEXTUAL=比較対象を併記した参考傾向。SUGGESTIVE=事前に固定した母数・時系列再現・不確実性条件を満たした研究上の示唆。INSUFFICIENT=小母数。CONFLICTED=期間/条件間の不一致。UNAVAILABLE=履歴不足・欠測。欠測を不得意とみなさない。SUGGESTIVEも能力の因果認定ではない。

P2のn>=30は初期の標本帯であり、強い能力ラベルの自動受入閾値としない。予想結果を見て閾値を後付け選定しない。

### R1: JPDB Profile Builder

予定騎手は対象日のPACI/KYIからrace_key_raw×horse_noに結合する。履歴はSED実騎乗者。予定騎手と実騎乗者を混同しない。対象日Dの履歴はrace_date < D、同日早いレースも使用禁止。

選択する軸は、芝ダート全体、今回の競馬場、今回のsurface×distance完全一致、馬場状態（開催前に未確定ならunknown/scenario）、BAC Course Masterの同定済み物理条件。距離帯や馬場bucketは独立したルール凍結まで追加しない。相互依存するvenue/distance/courseを5つの独立票として加算せず、redundancy_group_idでまとめる。

出力には出走候補母数、正常完走、勝利、連対、3着内、取消・除外・中止・降着レビュー、期間、最終観測日、対象日、source SHA、物理条件の可用性と欠測を保持。未分類と母数不一致はfail closed。

### R2: 記述傾向の解釈

当該条件の率と本人の他条件または同条件の他騎手の率を比較するが、双方の件数と馬質・機会差の可能性を明記。少数標本は保守的に扱い、3Y/365D/90Dの方向衝突をCONFLICTEDとする。多重比較・期間固定・年跨ぎ再現の研究基準は事前凍結する。原因推定・能力点・自動得意ラベルは作らない。

P3の最終オッズ、当該レースの最終市場、騎手能力残差、KYI総合指数などをsidecarの予想入力へ混ぜない。P3由来の診断値は非公開のresearch_diagnosticsに隔離する。

### R3: 独立sidecar Shadow

race_key_raw×horse_no×scheduled_jockey_codeで、最小のプロフィールJSONを生成。schema_version、target_date、target PACI SHA、SED generation/manifest SHA、Course Master SHA、asof_policy、各軸のn・観測成績・source_status・sample_support_status・direction・redundancy_group_idを持つ。

まずRaceNote本体のReader、KYI allowlist、Freeze、印、Confidence、CURRENT pointerを一切変更しない。別sidecarと検証receiptだけ作り、全馬coverage、ジョイン一意性、清浄入力、as-of、現行JOCKEY_TRENDとの冗長性を監査する。通常のRaceNoteはsidecarを読まずにFreezeする。これを予想効果とは呼ばない。

### R4: 同じレース・同じ入力でA/B

R3の技術ゲート通過後、未凍結の独立研究laneでJPDB有無を比較。既存のimmutable Freezeは更新しない。結果は両系統の予想凍結まで開かず、研究サンプルを事前固定する。導入による相対判断変更、誤った小母数断定、情報重複、過剰な加点、説明根拠、的中/3着内などを照合。50R程度は読解監査の初期単位であり、統計的な予想効果の証明には十分とは限らない。TRUE_FORWARDで新規期間の再現を確認する。

### R5: 本番採否

1. target PACI予定騎手/JPDB履歴騎手の別、race-horseキー、source hash、coverage、履歴遮断がPASS。
2. 禁止データ（対象結果・対象の最終オッズ/人気・未認証の因果能力値）を完全遮断。
3. 条件・標本・欠測の解釈監査とA/B効果が事前定義の受入基準を満たす。
4. RaceNoteに渡す版と差し込み先を明示承認し、Decision TraceにJPDB根拠を追跡可能にする。印・Confidence・Freezeを書き換えない。
5. production pointer更新は独立の変更承認。既存のv0.5.6/Gen0.3境界と過去Freezeを維持。

## 4. 今すぐ実施する最短工程

第一優先はR0/R1のprofile JSON契約と対象レース予定騎手とのジョイン試験。第二にR2の母数・比較・冗長性ガード。第三にsidecarの研究用実データE2E。第四に同一条件A/B。ここまでに能力スコアの完成、KYI各指数の純粋馬質化、大規模な別学習モデルの構築を必須としない。

## 5. 判定

既存P1/P2は固定source歴史集計E2E PASS。P3は診断・感度研究PASS、騎手能力因果認証保留。本再設計は提案のみでsidecar未実装、予想効果未確認、本番未承認。RaceNote/PWA/印/Confidence/Freezeは未変更。
