# EdgeDB / Training Edge — T7 最終廃止監査（2026-11-04）

> **結論: T7通常運用廃止 = 完了（範囲限定・証跡区分付き）**。EdgeDB/旧Training Edgeの通常計算・照合・日次取込・PWA公開依存を終了し、PACI-only Current/Pagesを実配信で受入済み。Drive退避資産の物理削除はユーザーによる実施報告に基づき、削除ファイル全件の独立readbackを実施したとは主張しない。

## 固定した確認範囲

- リポジトリ: `yukki0113/GPT`。最終機能修正を反映した `main` は `63a6133823d1b11716498f0c950f5c2018d70d1f`。本書は2026-11-04時点の証跡であり、将来のCurrent pointerを固定するものではない。
- 対象: JRDB Newspaper、個人/桃太郎PWA、EdgeDB専用生成・マッチング・配信、旧Training Edge/RL/my_indexの通常運用、接続済みDriveで確認できた旧保存先。
- 非対象: RaceNote独立凍結研究、RRDB/評価、Analysis Parquet・Historical Warehouse・PACI/Raw・JRDB Reader・Index Base・Fact Lite・Stats Mart・Eval・追切表示・Training Researchの独立正本、Git履歴、immutable revisionやReleaseの過去証跡。

## 監査ゲートと証跡

| ゲート | 結果 | 証跡 |
|---|---|---|
| T1–T4 廃止依存の切断 | PASS | [Phase 3 #2334](https://github.com/yukki0113/GPT/issues/2334)、`PHASE3_AUDIT.md`、`PHASE3_RESIDUAL_REFERENCES.tsv` |
| 最新の実行経路回帰 | PASS | [T4 run 41745399878](https://github.com/yukki0113/GPT/actions/runs/41745399878)。active root 915 tracked executable files、issues=0。35 pytest pass（47 subtests）、別の27 pytest pass、retired JS/UI PASS |
| PACI-only 日次生成 | PASS | [day run 41450479244](https://github.com/yukki0113/GPT/actions/runs/41450479244)、2026-11-01、24/24R、318頭、詳細過去走1,059件、audit PASS |
| Current 公開 | PASS | [Issue #2349](https://github.com/yukki0113/GPT/issues/2349)、[publish 41636124794](https://github.com/yukki0113/GPT/actions/runs/41636124794)。個人/桃太郎とも 2026-11-01 r9、24R、予想/イルカ0件（ユーザー承認の入力欠落許容） |
| 個人Currentの廃止addon残留 | PASS | [read-only audit #2356](https://github.com/yukki0113/GPT/issues/2356)、[run 41745044774](https://github.com/yukki0113/GPT/actions/runs/41745044774)。manifest `edge`/`edge_v05` = null、24/24Rでrace `edge_v05` state=null、候補レース/馬/IDすべて0 |
| 個人/桃太郎を含む全体Pages | PASS | [run 41745618075](https://github.com/yukki0113/GPT/actions/runs/41745618075)。main `63a6133...` のfocused tests、Prepare、Upload、DeployすべてSUCCESS。個人/桃太郎の配信組立・整合性検証を実施 |
| Current巻き戻し防止 | PASS | [PR #2355](https://github.com/yukki0113/GPT/pull/2355)。日付+revisionの単調前進を事前判定。旧 `publish/current.json`（2026-09-20 r2）の手動再公開は2026-11-01 r9に対して拒否されるテストを追加 |
| Current公開ルートの競合回避 | PASS | [PR #2357](https://github.com/yukki0113/GPT/pull/2357)。legacy Current / Skeleton / Momotaro / Kensho の4ルートを同一concurrency groupで直列化。変更後T4とPages SUCCESS |
| Drive退避資産の物理整理 | USER_REPORTED_DONE | [T6監査](T6_DRIVE_RETIREMENT_AUDIT_20261104.md)、[PR #2354](https://github.com/yukki0113/GPT/pull/2354)。ユーザーが退避先資産を削除したと報告。接続済みDriveではEdge専用削除候補0件、assistantによる削除0件 |
| 廃止関連Issueの残件 | PASS（確認時点） | `EdgeDB` / `Training Edge` / `PWA_REFACTOR` / `JRDB_NEWSPAPER` に関するopen Issue検索で0件。#2334・#2356はcompletedでclosed |

## ゼロの定義と残存物

**ゼロと判定したのは、廃止専用実行資産への現行通常経路の依存・起動、退役sourceの新規Current伝播、および上記アクティブrootの監査問題件数である。** Git全体の `edge` / `RL` という文字列、独立RaceNoteの実験、追切やJRDB `training_index`、過去の検証JSONに含まれる旧schema fieldが0件であるという意味ではない。

旧EdgeDB-only資産は最新の通常実行位置から撤去されており、証跡はGit履歴に残る。現在の `archive/retired-edge-training/ASSET_MAP.json` の35件は保存対象の旧Training Edge/独立証跡として扱い、戻して実行しない。`src/jrdb_newspaper_retired_sources.py` および退役source非伝播テストは引き続き現行の保護資産。

## 運用上の安全策

1. 正規の新聞日次処理は PACI → Base/history → optional independent addons → retired-source scrub → 個人/桃太郎Current → Pages。廃止済みEdgeDB Query/Registry/MatcherやTraining Edgeを呼び出さない。
2. Git-tracked `newspaper/publish/current.json` は旧2026-09-20 r2の要求であり、**現行Currentポインタではない**。再公開は実Release metadata/date/revisionを確認し、同日更新は必ずより新しいrevisionを使う。
3. 現行の公開ルートは同一concurrency groupを使い、古い日付・同日同revisionの発行要求はRelease変更前に拒否する。Kensho mergeはもともと現行同日より新しいrevisionを要求する。ユーザーが新日付を指定する通常公開は継続できる。
4. Releaseは可変のPWA配布cacheであり、Driveやimmutable revisionの置換ではない。旧auxiliary release sidecar（2026-10-31更新）には以前の監査値が残る場合がある。配布の真実は現行archive/metaとPagesの検証結果で判断する。

## 証跡上の限界・非ブロック事項

- T6削除の全ファイルID、退避先の内容、ゴミ箱/完全削除状態は独立して取得していない。**ユーザーによる削除実施報告**をもって手動整理アクションは完了扱いだが、技術的な全ロケーション不在証明ではない。
- ユーザーは2026-11-03にPWA動作問題なしと報告済み。ただし、その後再発行したr9について個人・桃太郎の実機画面/オフライン/同期を個別に再実査した記録はない。公開機械検証とユーザー報告は区別する。
- Web/HTTP外部からの公開Manifest再取得はこの実行環境でアクセスできず、Pages workflowでのReleaseからの構築・ハッシュ検証・デプロイ成功を本番配布側の監査根拠としている。
- 本件の完了は2026-11-04の通常運用廃止判定であり、将来別リポジトリ・別Drive接続から旧資産が発見された場合の再監査を免除しない。独立研究・履歴を一律削除する根拠にもならない。

## 最終判定

```text
T7_OPERATIONAL_DECOMMISSION       = PASS
T7_ACTIVE_RETIRED_DEPENDENCY     = ZERO_IN_AUDITED_SCOPE
T7_PACI_CURRENT_PUBLICATION      = PASS_2026-11-01_R9
T7_PERSONAL_RELEASE_RETIREMENT   = PASS_24R_ZERO_CANDIDATES
T7_PAGES_DEPLOYMENT             = SUCCESS
T7_CURRENT_ANTI_ROLLBACK         = PASS
T7_CURRENT_WRITER_SERIALIZATION  = PASS
T7_DRIVE_RELOCATED_DELETION      = USER_ATTESTED_NOT_INDEPENDENTLY_VERIFIED
T7_POST_R9_REAL_DEVICE_CHECK     = NOT_PERFORMED
T7_FINAL_STATUS                  = COMPLETE_WITH_EXPLICIT_EVIDENCE_LIMITS
```

通常運用としてのEdgeDB/Training Edge廃止はここで終結。新規開発や日次配布は既存のPACI-only/独立addonの契約へ従い、廃止研究の再起動には独立した新規設計審査を要する。
