# RaceNote Forecast Execution Thread Bootstrap v0.1

このスレッドは RaceNote の **pre-result prediction execution専用** とする。

## 1. 最初に読むもの

latest mainから次だけを読む。

1. `config/racenote_forecast_logic_current.json`
2. BTDAYなら `prospective_research_candidate.logic_contract`
3. BTDAYなら `prospective_research_candidate.runbook`
4. pointerが示す Decision Core schema
5. `FORECAST_READER_FACING_PROSE_v0_1.md`
6. BTDAY day-pool/history

旧versionの手順を足し合わせない。
active pointerが示すcontract/runbookを、そのversionの一つの文脈として使う。

## 2. Current BTDAY route

Current prospective logic:

`RaceNote-Human-Context-Reader-0.4.6-candidate`

通常経路:

```text
unused day selection
-> prepare request JSON
-> permanent prepare workflow
-> clean Reader
-> venue単位で連続予想
-> authored_decisions/<venue>.json を保存
-> 次会場へ自動継続
-> 全会場揃ったら permanent finalizer
-> Freeze / Validator / archive
-> STOP before results
```

通常運用では、BTDAYごとのtemporary workflowを作らない。

## 3. Prediction work

各レースで行うのは一つの統合判断だけ。

- race model
- ◎ ○ △1 △2 の通常支持4頭
- 独立▲
- 最終△2と最良の除外候補の境界確認
- 最終 ◎ ○ ▲ △1 △2
- sparse RRDB refs
- reader-facing reason

過去versionの hierarchy pass / promotion pass / Coverage state machineを
別工程として追加しない。

RRDBは全体文脈として読んでよいが、`rrdb_refs` は
**RRDBが最終判断を実際に変えた・明確に補強した馬だけ**を残す。
印馬一覧の複製にはしない。

## 4. Reader and prose

予想入力の正本はmarket-stripped clean Reader。全馬情報を読む。

Readerのツール上の分割方法は実装詳細であり、mandatory chunkや
一頭ずつのreadを通常手順にしない。

reader-facing proseは、印の順番をJSONのように読み上げるのではなく、
そのレースで重要だった具体的な競馬内容を一つの短評として書く。

RRDB / IDM / 内部指数名・role名は原則audit側に置き、読者向けには
その根拠となる競馬内容へ翻訳する。

## 5. Save and recovery

一会場を予想したら
`authored_decisions/<venue>.json`
をGitへ保存する。これが復旧点。

保存後は確認を求めず次会場へ進む。

実行が本当に途切れた場合だけ、既存authored venue filesを確認し、
最初の未保存会場から再開する。保存済み会場を再予想しない。

permanent finalizerは全会場が揃うまでは何も生成せず正常終了し、
揃った時だけdeterministic packagingを一度実行する。

## 6. Clean-blind boundary

Freeze完了まではtarget result、payout、final odds/popularity、
result join、post-race評価を開かない。

target-day marketもclean bind後のモデル入力には含めない。

結果確認・成績評価はFreeze後の別工程。

## 7. Responsibility boundary

モデル:
印、▲、boundary alternative、race model、horse case、reader-facing prose。

機械:
identity、hash、roster、schema、complete-card確認、bind、Freeze、
Validator、archive。

この境界を越えて機械が予想を作ったり、モデルがworkflow監査項目を
大量に手書きしたりしない。

## 8. Stop conditions

正常完了:
full card Freeze + Validator PASS + archive/readback完了。

途中終了:
保存済み会場と最初の未保存会場を報告する。確認待ちのために止まらない。

異常終了:
必要asset欠落またはdeterministic invariant FAILのみ。
結果を開かず、具体的なgate名と到達点を報告する。
