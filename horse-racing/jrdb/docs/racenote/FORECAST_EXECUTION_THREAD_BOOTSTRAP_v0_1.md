# RaceNote Forecast Execution Thread Bootstrap v0.1

このスレッドは RaceNote の **pre-result prediction execution専用** とする。

## 1. 最初に読むもの

latest mainから次の順に確認する。

1. `config/racenote_forecast_logic_current.json`
2. BTDAYなら `prospective_research_candidate.logic_contract`
3. BTDAYなら `prospective_research_candidate.runbook`
4. pointerが示す Decision Core / final record schema
5. `FORECAST_READER_FACING_PROSE_v0_1.md`
6. BTDAY day-pool/history

会話内の旧version手順を継ぎ足して使わない。
**active pointerが示すversionのcontractとrunbookだけを、そのversionの一つの文脈として使う。**

## 2. Pointerの使い分け

- BTDAY prospective research:
  `prospective_research_candidate`
- production/current forecast:
  `current_logic_version`

両者は別物。BTDAYにproduction pointerを代用しない。

Current BTDAY prospective:
`RaceNote-Human-Context-Reader-0.4.6-candidate`.

## 3. v0.4.6の仕事

予想実行スレッドが行うことは次だけ。

```text
unused day selection
-> DAY PREP
-> clean market-blind bind
-> complete Readerを読んで予想
-> venue batch save
-> 次会場へ自動継続
-> complete-day bind
-> preflight
-> Freeze
-> Validator
-> archive / reader-facing output
-> STOP before results
```

各レースではv0.4.6 contractに従って一つの統合判断を行う。

- race model
- ◎ ○ △1 △2 の通常支持4頭
- 独立▲
- 最終△2と最良の除外候補の境界確認
- 最終 ◎ ○ ▲ △1 △2
- reader-facing reason

過去versionの hierarchy pass / ▲ promotion pass / Coverage state machine を
別工程として追加しない。

## 4. Reader

予想に使う正本は market-stripped clean Reader。

全馬の情報を読む。短縮要約だけで予想しない。

ただしReaderをどうツール上で運ぶかは実装詳細。
通常運用で、

- mandatory chunk artifactを作る
- 1頭ずつ取得する
- chunkごとに監査する

ことは要求しない。

ツール出力制限で分割が必要なら、情報を落とさない範囲で実用的な単位に
分けて読めばよい。

## 5. 保存と継続

通常の復旧点は **1会場につき1回**。

`racenote_save_venue_batch_v046.py` がPASSしたら、その事実だけを理由に
停止したりユーザーへ再開指示を求めたりしない。

同一実行内で次会場へそのまま進む。

実行環境が本当に終了した場合だけ、
`racenote_save_venue_batch_v046.py --reconcile-only` で保存済み会場ファイルを
検証して進捗表を復元し、`batch_manifest.json` の `remaining_venues` から
再開する。保存済み会場の予想は作り直さない。
保存済み会場は再予想しない。

## 6. Clean-blind boundary

Freeze完了まではtarget resultを開かない。

開かないもの:

- 着順
- payout
- final odds
- final popularity
- result join
- post-race評価

target-day marketもclean bind後の予想入力には含めない。

結果確認・成績評価・ロジック変更はFreeze後に研究側で行う。

## 7. モジュール責務

機械処理はidentity・hash・roster・schema・完全性・Freezeを担当する。

機械処理は以下を決めない。

- 印
- ▲
- 境界代替馬
- race model
- horse case
- reader-facing prediction prose

予想判断はモデル、決定論的整合性はmoduleという境界だけを維持する。

## 8. 終了条件

正常完了:
full card Freeze + Validator PASS + archive/readback完了。

途中終了:
有効なvenue batchが残っているなら、保存済み会場と次の未保存会場を報告する。
確認待ちのために意図的に止まらない。

異常終了:
必要assetが実際にない、またはdeterministic invariantがFAILした場合のみ、
具体的なgate名と到達点を報告する。

結果を開いたり予想ロジックをその場で修正したりせず停止する。
