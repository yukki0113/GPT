# RaceNote v0.5.0 — A/B Pilot Thread Bootstrap

Status: READY TO USE  
Purpose: start a fresh forecast thread for the **v0.5.0 lane** of a same-BTDAY clean-blind A/B test.

## Paste this at the start of a new thread

このスレッドは、RaceNote clean-blind A/B比較における **v0.5.0-candidate専用予想スレッド** として使用します。

対象は、すでにStage E A/B harnessで確保・封印された同一BTDAY/sessionです。

まずGitHubの正本を確認し、対象A/B sessionの以下を特定してください。

- selection_id / BTDAY id
- target_date
- session_id
- base_main_sha
- shared clean Reader manifest SHA
- expected venues / race roster
- Lane B = `RaceNote-Human-Context-Reader-0.5.0-candidate`

このスレッドでは **v0.5.0 candidate Readerのnormal_viewだけ** を通常の予想入力として使い、対象日の全レースをclean-blindで予想してください。

### 厳守事項

- v0.4.6 laneのbranch、PR、authored_decisions、frozen成果物、印、理由文、decision traceを見ないでください。
- 別スレッドや過去会話にある同一BTDAYの予想内容を参照しないでください。
- sibling laneの予想を比較・模倣・補正しないでください。
- 使用してよいのは、A/B sessionで封印されたshared clean evidenceから決定論的に生成されたv0.5.0 normal_viewと、v0.5.0 Reader契約だけです。
- provenance/detail sidecarを通常の第二証拠面として読まないでください。明示的な監査・detail確認が必要な場合以外、予想入力に混ぜないでください。
- target結果、払戻、最終人気、最終オッズを開かないでください。
- 予想途中で結果確認を行わないでください。
- tierを数値weightや機械的投票に変換しないでください。
- PRIMARY / SECONDARY / CONTEXT_ONLYは情報提示上の優先度として扱い、最終判断はHuman-Contextで統合してください。
- ◎ ○ ▲ △1 △2 の5頭を各レースで選出し、▲はmainlineとは独立したsingle-shot caseとして判断してください。
- 最終△2とstrongest excluded alternative/nullの比較を残してください。
- RRDBは判断を materially 変えた場合だけ疎に参照してください。
- reader-facing reasonは自然な競馬分析文にしてください。

### v0.5.0 Reader上の注意

通常のmodel-facing入力は `normal_view` のみです。

Stage C/DでREDUNDANT_HIDDENまたは既定非表示となった情報を、provenanceから常時読み戻してv0.4.6相当へ戻さないでください。

ただし、missingness・source divergence・監査上の整合確認が必要な場合は、Stage E harnessの規定に従いprovenanceを監査用途で確認できます。

### 実行単位

会場ごとに連続して予想し、各会場完了後にLane B専用のauthored_decisionsへ保存してください。

既存のStage E A/B harnessが定めるLane Bパス・保存契約・Freeze手順に従ってください。

### Freeze

全会場が揃ったら、Lane Bとして独立Freezeしてください。

Freeze完了時には必ず、

- logic_version = `RaceNote-Human-Context-Reader-0.5.0-candidate`
- market_blind = true
- result_opened = false
- target_market_opened = false
- status = `FROZEN_CLEAN_BLIND`

を確認してください。

### 完了報告

完了時は次だけを簡潔に報告してください。

- selection_id / target_date
- session_id
- 完走レース数
- Lane B freeze status
- commit SHA / branch / PR
- Validator結果
- 未解決事項

このスレッドではA/B比較や結果評価は行いません。
v0.4.6側のFreeze完了後、別の統合・評価スレッドで比較します。
