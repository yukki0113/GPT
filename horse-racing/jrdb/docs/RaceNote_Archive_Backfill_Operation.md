# RaceNote Archive backfill operation

RaceNote Archiveのhistorical coverageを年単位で拡張する運用メモです。

## Goal

- 月次Archive shardは従来どおり immutable GitHub Release として配布する。
- 1年分のbackfillではAnalysis Liteを1回だけ取得する。
- accepted JRDB Warehouse generationをmaterializeして同一Actions run内で共有する。
- 既存のpublishable shardはresolverでvalidationしてSKIPする。
- 未整備月だけfull-month build / full scan validation / Release publishする。
- 途中失敗後の再実行では、既にpublish済みの月をSKIPして残りから再開できる。

## Safety

- Archiveはbase RaceNote v0.2だけを保存する。
- final RaceNote v1.0はrequest時にcurrent Analysis Lite / Stats Mart enrichmentを適用する。
- 2010--2025の**新規**Archive生成元は `10_warehouse/jrdb/v1/current.json` が指すaccepted immutable Warehouseである。
- Warehouse reader / adapterだけを使い、consumer独自のDuckDB/fixed-width解釈を追加しない。
- 2010のprevious-resultが2009以前を参照する場合だけ、該当ZED/ZKB行を明示Raw boundary inputとして追加する。対象BAC/KYI/CHA/CYBをRawへdowngradeしてはならない。
- 2011--2025ではRawを取得しない。annual Rawはrollback / audit / dual-read / 2010 boundary / legacy immutable reproduction専用である。
- expected race identityはAnalysis Liteの `race_key / race_date / venue_code / race_no` のみを使用し、対象レース結果値は使用しない。
- `full_month` / `publishable` / exact identity match / provenance complete / full scan PASSを満たさないshardは公開しない。
- GitHub Releaseはimmutableとして扱い、同一tagを上書きしない。

## Coverage order

初回は2025年を対象にし、既存の2025-08 shardをvalidationしてSKIPする。2025年が完了したら2024年から2016年へ年単位で遡る。

Release resolverはcoverageが100 shardを超えても探索できるようpagination対応を必須とする。

## Backfill input contract

`backfill_racenote_archive_year.py` は次を必須とする。

```text
--warehouse-current <materialized 10_warehouse/jrdb/v1/current.json>
--warehouse-asset-root BAC=<root>  （KYI/CHA/CYB/ZED/ZKBも同様）
```

currentとfinal manifestは必ず同一immutable generationで検証する。asset rootはmanifestの`relative_path`を保持するmaterialized read-only cacheであり、Archive builderはParquetを再生成・更新しない。2010だけは`--boundary-raw-dir`を明示し、必要なpre-2010 ZED/ZKB年次Rawを用意する。2026をWarehouse Archive builder/backfillへ渡すとfail closedする。

`[RACENOTE_ARCHIVE_YEAR_BACKFILL]` workflowは、read-only materialization用の`warehouse_root_url`を受け取り、accepted current/manifestとmanifest記載asset全件を検証してから実行する。2010では追加で`boundary_raw_root_url`を受け取り、pre-2010 `ZED/ZED_2009.zip` と `ZKB/ZKB_2009.zip` を同一cache rootへmaterializeする。これらのURLはArchive provenanceやRelease assetへ書き込まない。

## Cutover gate

backfillをWarehouse標準にする前に、Raw既存builderとWarehouse builderで2018代表月・2025代表月・2010境界月を各2回buildし、`audit_racenote_archive_raw_vs_warehouse.py`で次をPASSさせる。

- race identity / race count / Archive schema / bundle semantic SHA
- full scan、`full_month`、`publishable`、provenance complete
- Warehouse repeated-build determinism
- 2010 boundary key数・Raw boundary file provenance

既存immutable ReleaseはresolverがvalidationしてSKIPする。Warehouse cutoverは新しく生成する月だけに適用し、既存Archiveを上書き・再公開しない。
