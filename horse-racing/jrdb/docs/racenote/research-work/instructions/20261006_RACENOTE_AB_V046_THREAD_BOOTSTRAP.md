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

予想は、まず各レースのcomplete clean Readerを全頭ぶん読み、普通の競馬予想として
「このレースは何で決まりそうか」を考えるところから始めます。能力、近走内容、
脚質と位置取り、展開、距離・馬場適性、状態、必要に応じたRRDB文脈を一つの
race modelとして統合し、その見立てから ◎ ○ ▲ △1 △2 の5頭を決めてください。

◎・○・△1・△2は通常の本線4頭です。▲だけはその序列とは別に、この組み合わせで
条件や展開が噛み合った時に勝ち切れる非対称な一頭として選びます。最後に△2と
最も迷った除外馬を一度だけ比較し、5頭を確定します。

Decision Coreは、この予想を保存するための記録です。欄を埋めるために判断を作るの
ではなく、実際にそのレースを読んで決めた内容をそのまま記録してください。

- `race_model` には、そのレースで勝敗を分けそうな構図を書く。
- `mainline_cases` には、本線4頭を残した実際の根拠を書く。
- `single_shot_case` には、▲が本線勢を上回る具体的な勝ち筋を書く。
- `boundary_review` には、△2と最有力除外馬の実際の比較を書く。
- `reader_facing_reason` には、以上を読者向けの自然な短評としてまとめる。

数字や指数は判断を説明するのに役立つ時だけ使い、Reader項目の羅列を理由文の代わり
にしないでください。短くても、その馬・そのレースについて何を評価したかが伝わる
文章を優先します。

RRDBは他のReader情報と同じく文脈の一部として読み、判断を materially 変えた、
または解釈を明確にした場合だけ `rrdb_refs` に残します。

A/Bの独立性については、v0.5.0 laneのbranch、PR、authored/frozen成果物、印、
理由文、decision traceを予想入力として参照しません。同一BTDAYについて別スレッド
や過去会話に予想内容があっても参照せず、A/B sessionで封印されたshared clean
evidenceとv0.4.6 Reader契約だけから独立して予想します。target結果、払戻、最終人気、
最終オッズもFreeze完了まで開きません。

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
