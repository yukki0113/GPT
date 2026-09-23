# RaceNote Archive backfill operation

> **CURRENT STATUS — 2026-09-23:** this documents the existing legacy Raw-oriented annual backfill implementation. It is retained for audit/rollback compatibility and is not the current 2010–2025 Historical source-of-truth contract. New Historical reads use the accepted JRDB Warehouse.


RaceNote Archiveのhistorical coverageを年単位で拡張する運用メモです。

## Goal

- 月次Archive shardは従来どおり immutable GitHub Release として配布する。
- 1年分のbackfillではAnalysis Liteを1回だけ取得する。
- annual Raw cacheを同一Actions run内で共有し、月ごとの再取得を避ける。
- 既存のpublishable shardはresolverでvalidationしてSKIPする。
- 未整備月だけfull-month build / full scan validation / Release publishする。
- 途中失敗後の再実行では、既にpublish済みの月をSKIPして残りから再開できる。

## Safety

- Archiveはbase RaceNote v0.2だけを保存する。
- final RaceNote v1.0はrequest時にcurrent Analysis Lite / Stats Mart enrichmentを適用する。
- <=2025のArchive生成元はannual Raw reconstruction。
- expected race identityはAnalysis Liteの `race_key / race_date / venue_code / race_no` のみを使用し、対象レース結果値は使用しない。
- `full_month` / `publishable` / exact identity match / provenance complete / full scan PASSを満たさないshardは公開しない。
- GitHub Releaseはimmutableとして扱い、同一tagを上書きしない。

## Coverage order

初回は2025年を対象にし、既存の2025-08 shardをvalidationしてSKIPする。2025年が完了したら2024年から2016年へ年単位で遡る。

Release resolverはcoverageが100 shardを超えても探索できるようpagination対応を必須とする。
