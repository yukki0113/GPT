# BRDB GPT workflow

## Thread bootstrap

1. root `.gpt/GITHUB_OPERATION_POLICY.md`
2. `horse-racing/brdb/README.md`
3. `horse-racing/brdb/.gpt/CONTEXT.md`
4. 本書
5. **基本設計** `docs/BRDB_BASIC_DESIGN_AND_RESEARCH_POLICY_20261120.md`
6. `docs/BRDB_RRDB_INHERITANCE_v0_1.md`、対象Issue/PR・現行契約・source・tests
7. latest `main` と作業branch差分、既存Draftの範囲

過去の会話/要約をGitの現行正本の代替としない。JRDB / 騎手DBの参照は実際の対象ソース・契約を確認する。

## Development priorities and gates

**目的**：既存RaceNoteの過去走に偏った評価に、独立した血統観点を追加する。既走馬での増分価値、および新馬戦・未出走馬の事前情報による研究予想の可能性を検証する。両方とも**実証済みの主張ではない**。

通常レース:
1. 既存過去走baselineとBRDBの独立根拠を記録する。
2. 条件変化・血統ペア・近親・馬場の根拠を根拠ID単位で提示する（優劣や適性の未検証断定はしない）。
3. 予測上の追加価値、市場人気帯への偏り、校正・ROI等を別途検証する。

新馬戦:
1. JRA/JRDBの新馬レース判定と各馬初出走の区別、父産駒初戦、兄姉/近親初戦、時点安全性をまず監査する。
2. 全馬非採点のデビュー専用candidateを独立契約で作成する。非該当/不足/不明を明示する。
3. 一般産駒集計を新馬戦適性と同一視しない。既存の自信度Zは本番で維持し、予想は研究枝で事前固定する。
4. 騎手DBは独立source/契約に従い、結合はRaceNote側で行う。騎手データや調教が既に利用可能だと仮定しない。

共通の合格条件：identity、source SHA、as-of、時間外漏洩防止、母集団/低N、同一馬・親族重複、時系列holdout、独立baseline、再現テスト、consumer非干渉。既存M6/M7の未承認状態を変えない。

## GitHub routing

リポジトリ共通方針に従う。

- A: Read/Audit
- B: Git Change（通常のdocs/source/test/schema。最新blob SHAを確認）
- C: Pure Deterministic Execution（固定入力・ローカル可能な検査）
- D: Actions-Native（Secrets/大容量/正式凍結やrun証跡が必要な場合）

GitHub text更新のためにIssue/Actionsを安易に起動しない。別スレッドとの競合はlatest main再読込/fast-forwardで解決、force禁止。

### Parquet / DuckDB 実行経路 — 2026-11-23

`horse-racing/brdb` のcanonical query / validation / conversionは共通 `tools/data-storage/` を利用する。GPTのPython 3.13 Linux x86_64環境で`check-deps`が未充足なら、**第一復旧経路はregistryでSHA固定されたprivate Drive 3-wheel bundle**とする。GitHub `main` のregistry・bootstrap script・Phase 2 runbookを再取得し、native Drive connectorで取得したZIPのID/size/SHAを照合後、新規隔離venvへoffline installし、`check-deps`と対象moduleのauditを確認する。互換venvがあればそのまま再利用する。

対応外環境・Drive取得不可・検証失敗時は、勝手に未知のwheelをinstallせず通常のpinned requirements復旧を一度試す。管理runtimeでそれもblockedの場合に限り、入力の再現可能性と非公開データ境界を確認して既存`[DATA_STORAGE_FALLBACK]`を使用する。Actions-native固有のSecrets/取得/凍結/正式監査は従来どおりD系を維持。**JRDBでのwheel E2E PASSを、このProject固有の実データE2E PASSと読み替えない。** 予想のas-of、サンプル、identity、leakage、publication contractは変更しない。詳細はroot `.gpt/GITHUB_OPERATION_POLICY.md` C-1と`tools/data-storage/docs/JRDB_CHATGPT_OFFLINE_RUNTIME_PHASE2_20261123.md`。

## Data / source boundary

- Source order: ①JRDB canonical既存血統資産、②BRDB immutable master、③明示的にreviewされた外部情報。馬名一致から親子/祖先IDを推定しない。
- JRDB固定長parserと `tools/data-storage/` のParquet/DuckDB共通処理を再実装しない。
- PrivateなM7相対馬統計等はGitHub・公開CIアーティファクトに持ち込まない。GitHub CIは合成入力を使う。
- 研究の歴史結果は通常 `race_date < target_date` を要求。データ配信・更新時刻が証明できなければ `AS_OF_UNVERIFIED`、prediction-safeへ上げない。

## Review/consumer boundary

```text
BRDB canonical facts + validated historical evidence
  -> BRDB non-scoring review / candidate research
  -> separately approved Reader / versioned adapter
  -> RaceNote evidence orchestration (past runs + blood + jockey profile)
  -> separately approved Newspaper/PWA display
```

- 全頭reviewを基準とし、RaceNoteの疎な予想CSVをBRDB全頭データと誤結合しない。
- frozen `brdb-review-v0.1`、CURRENT、M6/M7、既存デプロイへの黙示変更禁止。
- 公開前にschema/contract・実レースのstrict identity・非干渉・表示文言/実機・明示承認を得る。
- Phase 0–4の初期順序は履歴としてREADMEに残し、今後の研究優先順位には基本設計第7節を用いる。
