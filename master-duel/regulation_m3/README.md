## 2026-11-10 追記: SQLite候補取り込み (M3-2)

`persistence.prepare_candidate_import` を追加。前世代ZIPの完全性を検査し、検証状態が `UNVERIFIED_SOURCE` の規制候補だけを既存SQLite v1の `banlist_snapshots` / `banlist_entries` に**追加専用**で投入。候補の自動 `GAME_VERIFIED` 化・既存ID上書き・存在しないカードID・所持履歴変化を拒否する。カード本文を含む保護9テーブルの全行ダイジェスト一致、SQLite integrity と foreign key 検査、新ZIP再展開を実施する。処理はローカル候補ZIPを返すだけでDrive HEADは変えない。

**更新後の本番状態:** 先行M2で非公開Drive HEADは世代2（所持5種類・9枚）になっている。以下の当初「世代1」「所持0件」は初期設計時点の履歴。今後のM3候補投入では、必ず最新世代2を親とする。旧世代ZIPを使用した巻戻しは禁止。

2026-11-05改訂差分の9カードについて、公開の改訂リストと非公開vectorのID/値を照合して9/9一致。これにより215件すべてのゲーム内確認が済んだとは**決して扱わない**。<https://mdm.app.duellinksmeta.com/articles/news/october-26-2026/master-duel-forbidden-list-update> と <https://game8.jp/yugioh-masterduel/423063> を参照。OCGサイトはMDの正本に流用しない。

# M3 — 日付付きMD禁止制限と生成CPの安全評価

基準: 2026-11-10。ユーザーの所持申告を待たずにM2と並行開発する。M3は非公開Driveの禁止制限候補を、ゲーム内で確認済みの規制として誤採用しないことを最優先とする。OCG/TCGのリミットレギュレーションをMDへ流用しない。

## 現状

- 私的Drive GPT/MasterDuel/source/current.vector.json は、2026-11-05付・215件の明示規制候補。SHA-256: 2651601cb3bf9b66dde522eff92207968c9b9f63f4b82632910ccacdf5210781。実カードマスター13,948件に対する215 IDの存在照合は215/215 PASS。
- ファイル自体には出典・検証状態・適用形式・完全リストであることを証明する情報がない。候補215件は個別の合法性保証をしない。未掲載カードも無制限3枚とは扱わない。
- 公式SNSの2026-11-05適用告知は外部で確認したが、215件の全件一致はゲーム内で未検証。完全に独立した公式一覧の読取完了までは候補として保持。
- 現行本番SQLite世代1の banlist_snapshots/banlist_entries は未登録。候補は別の私的JSONとして扱うことが可能。本M3のコード・架空テストの導入で本番HEAD/ZIPを切替えない。

## スナップショットの契約

schema_version=1、snapshot_id、format_id（MD_から始まる形式ID）、effective_on（YYYY-MM-DD）、checked_at（UTC offsetつき）、source、source_sha256、verification（UNVERIFIED_SOURCE / GAME_VERIFIED）、rules（konami:ID -> 0/1/2/3）。

- legacy_vector_to_candidate(raw_bytes, checked_at=...): Driveの既存date/regulation形式を検証し候補スナップショットへ変換。決してGAME_VERIFIEDにしない。元ファイルのSHAを残す。実変換結果は非公開領域でのみ管理。
- resolve_limit(snapshots, card_id=..., as_of=..., format_id=...): 対象日以前で最も新しい該当形式を選択。新しい未検証snapshotがあれば古い検証済snapshotへの黙示フォールバックを禁止。同一施行日の二重登録はAMBIGUOUS_SNAPSHOT。
- VERFIED（綴りはAPI上 VERIFIED）時だけallowed 0..3を返す。候補はCANDIDATE_ONLY + candidate_max_copies、未掲載はUNLISTED_UNKNOWN、適用版がなければNO_APPLICABLE_SNAPSHOT。
- 明示した制限エントリ以外は、たとえsnapshot全体がGAME_VERIFIEDと表示されてもUNKNOWNにする。禁止制限の一覧が不完全なまま3枚を黙示適用しない保守的な運用。

## 所持数との接続

assess_deck_with_m3(db_path, recipe, snapshots, as_of, format_id, ...) は既存deck_assistant.cost.assess_deckへ、ゲーム内確認済みのカードに限りallowed_copiesを渡す。カードごとのregulation（証拠/適用日/確認状態）とavailable_owned_copies（確定可能時のみ min(所持、上限、3)）を付加する。所持UNKNOWNは0と推定しない。規制UNKNOWNならPASSにしない。

## 生成CPの契約

validate_cp_policy(policy) はeffective_on、checked_at、source、verification、N/R/SR/URごとのcp_per_cardを要求。現行例として1枚につき同レアリティの30 CPが広く説明されているが、本番の最新ゲーム画面の独立照合がないため、デフォルトとしてGAME_VERIFIEDをセットしない。外部候補から導入する場合、verification=UNVERIFIED_SOURCEにする。

カード生成の通貨はCP-N、CP-R、CP-SR、CP-URで独立しており、例えばCP-SR 90の不足はCP-Nで埋められない。cp_budget_by_rarity={"UR":0,"SR":300}のように各通貨を個別に判定する。生成不能カードの判定は既存カタログのcraftableも参照するが、UNKNOWNなら確定評価しない。未確認CPポリシーに基づく見積りは結果に示せるが、確定した予算PASS/FAILとしない。

既存の単一数値cp_budgetは互換APIであり、実際の異なるCP通貨の残高としては使わない。M3ではcp_budget_by_rarityを使用する。

## 確認手順と未完

1. 私的Drive sourceフォルダからvectorを取得しSHA検証。候補に変換し読み取り専用で全215 IDを本番カードマスターと照合する。
2. 利用者がMDゲーム内または完全性が検証された正規資料で実見した範囲について、出典・日付・対象形式を整理する。部分的な実見だけでsnapshot全体をGAME_VERIFIEDにしない。
3. 日付、規制、出典の版差分を監査して私的スナップショットを作る。本番ZIPへの禁制テーブル昇格は、別途M2と同じバックアップ/独立読戻し/単一ライター処理が整った後に行う。
4. M2所持申告完了後、同じ現行snapshotを使って採用枚数・CPの確定判定を行う。M4/M5/M6へ結果と不確実性を渡す。

本フェーズはコードの受入と非公開候補監査が中心。実施済みと未検証を混同しない。実カード一覧・全文・所持情報はGitHubへ公開しない。


## M3候補スナップショットをSQLiteへ保存（第2段階）

\`stage_candidate_snapshot(db_path, snapshot)\` は**隔離された作業コピー**のSQLiteだけを受け付け、MD_STANDARD・UNVERIFIED_SOURCEの候補を \`banlist_snapshots\` / \`banlist_entries\` へトランザクションで保存する。候補をGAME_VERIFIEDへ昇格しない。KONAMI ID完全一致、施行日の重複、別内容の同一snapshot ID、不明カード、途中失敗時のROLLBACKを検査する。同一内容の再送はALREADY_PRESENTとなる。 \`read_candidate_snapshot\` は件数と0/1/2/3の分布を読み戻す。

適用の安全手順：最新Drive HEAD・参照ZIPのSHA/DBを独立確認→ZIPをプライベート作業コピーへ展開→legacy_vector_to_candidateを通した未検証候補をstage_candidate_snapshotで保存→更新済みSQLiteのintegrity/foreign_key・所持/効果件数不変・215件の読み戻し→新しい不変ZIP作成→Driveで旧ZIPとHEADを別ファイルにバックアップ→新ZIPとmanifestを別ファイルで保存し独立に読み戻し→単一ライターを維持してHEAD最終照合・昇格→再読み戻し。確認不能時はHEAD切替禁止。コードはDriveを書き換えない。

本番に保存しても候補215件は未検証のまま。M3のゲーム内規制確定は別途、正式な公式データと差分を検証して実施する。M2の所持5件/9枚は変更禁止。
