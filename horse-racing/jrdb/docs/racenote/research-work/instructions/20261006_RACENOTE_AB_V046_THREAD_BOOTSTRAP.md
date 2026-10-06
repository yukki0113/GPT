# RaceNote v0.4.6 — A/B Pilot Thread Bootstrap

Status: READY TO USE  
Purpose: start a fresh forecast thread for the **v0.4.6 lane** of a same-BTDAY clean-blind A/B test.

## Paste this at the start of a new thread

このスレッドは、RaceNote clean-blind A/B比較における **v0.4.6専用予想スレッド** として使用します。

対象は、すでにStage E A/B harnessで確保・封印された同一BTDAY/sessionです。

まずGitHubの正本を確認し、対象A/B sessionの以下を特定してください。

- selection_id / BTDAY id
- target_date
- session_id
- base_main_sha
- shared clean Reader manifest SHA
- expected venues / race roster
- Lane A = `RaceNote-Human-Context-Reader-0.4.6-candidate`

このスレッドでは **v0.4.6 Readerだけ** を使用して、対象日の全レースをclean-blindで予想してください。

### 厳守事項

- v0.5.0 laneのbranch、PR、authored_decisions、frozen成果物、印、理由文、decision traceを見ないでください。
- 別スレッドや過去会話にある同一BTDAYの予想内容を参照しないでください。
- 使用してよいのは、A/B sessionで封印されたshared clean evidenceとv0.4.6の正式Reader契約のみです。
- target結果、払戻、最終人気、最終オッズを開かないでください。
- 予想途中で結果確認を行わないでください。
- 現行のv0.4.6 horse-selection semanticsを変更しないでください。
- ◎ ○ ▲ △1 △2 の5頭を各レースで選出し、▲はmainlineとは独立したsingle-shot caseとして判断してください。
- 最終△2とstrongest excluded alternative/nullの比較を残してください。
- RRDBは判断を materially 変えた場合だけ疎に参照してください。
- reader-facing reasonは自然な競馬分析文にしてください。

### 実行単位

会場ごとに連続して予想し、各会場完了後にLane A専用のauthored_decisionsへ保存してください。

既存のStage E A/B harnessが定めるLane Aパス・保存契約・Freeze手順に従ってください。

### Freeze

全会場が揃ったら、Lane Aとして独立Freezeしてください。

Freeze完了時には必ず、

- logic_version = `RaceNote-Human-Context-Reader-0.4.6-candidate`
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
- Lane A freeze status
- commit SHA / branch / PR
- Validator結果
- 未解決事項

このスレッドではA/B比較や結果評価は行いません。
v0.5.0側のFreeze完了後、別の統合・評価スレッドで比較します。
