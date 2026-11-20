# BRDB 基本設計・研究開発方針 — 2026-11-20

Status: **PROJECT DESIGN / RESEARCH POLICY**。本書は開発目的と検証・consumer 境界を定める。既存 frozen contract、CURRENT、RaceNote、Newspaper、PWA を変更・昇格する許可ではない。

## 1. 開発目的（最上位）

RaceNote は現状、過去走・既走パフォーマンスを主たる判断材料とする。その強みを維持しつつ、過去走ベースでは捉えにくい要因を**独立した evidence lane** として追加する。

1. **既走馬**：過去走評価と異なる角度から、条件変更・血統的特性・配合・近親などの再検討材料を供給する。実績豊富な馬・市場人気馬への評価集中を緩和できるか検証する。
2. **新馬戦・未出走馬**：過去走が存在しないことと評価材料が存在しないことを区別する。父産駒の初戦実績、母父、配合、近親、血統の早期能力発現に関する**事前に入手可能な根拠**を提供し、RaceNote の現行自信度Z領域を研究対象に含める。
3. **騎手プロファイルDBとの将来併用**：血統と騎手の条件別特性をそれぞれ独立の根拠としてRaceNoteが受け取れるようにする。BRDB は騎手DBの再実装や両者の暗黙スコア加算をしない。
4. **評価の分散と市場差の実証**：血統情報が予測精度、校正、既存RaceNoteへの増分、人気・オッズとの関係に寄与するかを実測する。血統上の可能性と馬券の妙味・収益性は別に検証する。

上記は**研究目標であって、現在達成した性能の主張ではない**。

## 2. 責務とアーキテクチャ

```text
JRDB canonical pedigree / guarded external pedigree source
    + JRDB Analysis historical starts/results (strict point-in-time)
      -> BRDB canonical identity / immutable facts / condition statistics
      -> descriptive evidence: ①父 ②母父 ③配合 ④近親 ⑥地域/⑦内包血統（補足）
      -> non-scoring integrated Blood Review / reviewed candidate contracts
      -> versioned BRDB Reader / consumer adapter (explicit approval only)
                        |
                        v
         RaceNote evidence orchestration (consumer responsibility)
            |- existing past-performance evidence
            |- BRDB blood evidence (separate lane)
            |- jockey-profile evidence (separate lane, external DB)
            |- additional pre-race evidence (when independently available)
            -> decision / confidence / selection (RaceNote responsibility)
                        |
              Newspaper / PWA display (separate release gate)
```

BRDB は根拠、比較母集団、対象条件、件数、不確実性、時点、provenance を返す。予想印、順位、確率、期待回収率、RaceNote 自信度の決定はBRDBの責務外。レビュー文言やTipsを生成する場合も観測・仮説・検証済み知見を識別し、根拠IDに紐付ける。

**原則は対象レース全頭**。市場人気や既存RaceNote選抜5頭を入口フィルタにしない。母集団を人気上位に限定しない。

## 3. 2つの評価経路

### A. 既走馬：独立根拠と増分価値

- 過去走の能力・適性推定をBRDBが上書きしない。過去走からの評価と血統由来の評価を個別に監査可能にする。
- 条件変更（芝/ダ、距離、馬場、場、コース）で過去走では説明しきれない候補を提示する。ただし「今回向く」などの適性結論は時系列検証を通過した項目に限る。
- 人気・オッズは独立した評価/市場比較に使用し、未来の確定オッズ・払戻を出走前入力へ逆流させない。
- 従来のRaceNote単独を baseline、RaceNote+BRDB を対照とし、騎手DB併用時には追加のアブレーションを行う。的中率だけでなく校正・対象馬の分布・人気帯・条件別・収益性を分離して見る。

### B. 新馬戦：デビュー専用evidence path

- 過去走欠損を0点や適性否定として扱わない。新馬戦に適した比較母集団と特徴量契約を独立させる。
- 優先研究軸：父産駒の**初出走/新馬戦**成績、母父系、父×母父/系統ペア、兄姉・母方近親の初戦/早期成績、年齢・月齢・時期・芝ダ・距離・競馬場・馬場条件。一般の全出走勝率をそのまま「新馬戦適性」と読み替えない。
- 競馬法上の「新馬戦」と個体の「初出走」は同一ではないため、対象レース区分と各馬の初出走状態を別フィールドで扱う。初戦までの観測可能性・母集団の期間・供用年・個体IDを記録する。
- 騎手の新馬戦実績は騎手DB側で作成し、BRDBとは重複独立性を検証してからRaceNote側で統合する。調教・厩舎情報は正式ソースがあって時点安全が担保された場合のみ別laneで追加する。**BRDB単独で未収集のデータがあると仮定しない。**
- 研究初期の新馬戦は従来の自信度Zおよび本番予想仕様を維持し、**分離した研究予想/評価**として事前固定・事後照合する。実証と明示承認なしにZを解除しない。

## 4. 研究から予測利用までのゲート

- **G0 Source/identity**：JRDB 8桁 blood registration `horse_id`、対象`race_key`/`horse_no` を厳密照合。馬名fallback・推測ID・未検証親子経路を禁止。データ欠損・低Nを隠さない。
- **G1 Descriptive research**：出走・勝利・3着内などの観測値、時系列範囲、条件スコープ、比較対象、重複集団、`NO_SAMPLE`/`LOW_SAMPLE`/`SOURCE_UNAVAILABLE` 等の状態を提供。出走数が異なる5階層を足さない。観測相関を因果/能力へ昇格させない。
- **G2 Point-in-time audit**：対象発走前に利用可能なプロフィール・親子情報・分類・研究ポリシーのみを使用。結果は原則`race_date < target_date`。同日異レース等の利用可否も時刻が証明できなければ除外。現在の情報を歴史時点へ無断で遡及させない。`AS_OF_UNVERIFIED` は研究専用、`prediction_safe=false`。
- **G3 Scientific validation**：時系列holdout、事前固定の特徴量・閾値、複数仮説探索への対策、母集団の年・場・クラス・距離/芝ダ・人気帯・種牡馬偏重の検査、サンプル独立性、カバレッジ、効果の不確実性。新馬戦は別レポート・別baselineを必須とする。
- **G4 Incremental value**：過去走のみ、血統のみ、騎手のみ、組合せの比較を同じrace/date/field splitで実施。過去走への増分、新馬戦での無情報baseline超過、市場との差の再現、必要ならオッズ時点を固定した期待値/ROIを別途評価。
- **G5 Consumer acceptance**：契約固定、JSON schema、18/18等の全頭identity、strict fail-closed、Newspaper非干渉、文言確認、実機表示、後方互換テスト、個別の公開・本番昇格承認。研究PRやPWA表示PRの存在は承認とみなさない。

`prediction_safe=false`、`production_authorized=false`、`AS_OF_UNVERIFIED` を暗黙変換しない。真の事前予測に使えると実証するまで、表示用候補でも「予想の根拠」として製品上に流さない。

## 5. 評価・報告の観点

最低限、以下を固定した再現可能なレポートとする。

- 既走馬と新馬戦（初出走を別記）の件数、全頭coverage、理由別欠損、情報源ごとのas-of可否。
- 条件別各根拠の件数/ユニーク馬数/年数/父系数、重複ID・条件スコープ、観測結果と比較baseline。
- 検証セットにおける評価の分布、人気上位への集中度、人気帯別成績、RaceNote単独からの増分、校正・不確実性。
- 新馬戦：従来Z運用をbaselineとし、**研究上のカバレッジ増加**と**予測性能の向上**を別々に測る。根拠が生成できても当たるとは限らない。
- コスト/レイテンシ、厳密再演可能なinput SHA、source commit、logic/schema version、output SHA。

評価指標、比較期間、採用閾値は今後の独立した研究仕様として事前登録する。現段階で改善率や閾値の達成を主張しない。

## 6. 既存実装との関係・変更不可境界

- `brdb-review-v0.1` frozen、BRDB CURRENT、RaceNote P1/P2、M6 [#2395](https://github.com/yukki0113/GPT/issues/2395)、M7 [#2628](https://github.com/yukki0113/GPT/issues/2628) の状態は本書で変更しない。
- `brdb/research-cross-discovery-v02-20261119` / Draft [#2655](https://github.com/yukki0113/GPT/pull/2655) の馬場横断研究v0.6と表示projectionは**研究候補**。本書によって予測安全性やconsumer連携が承認されるものではない。
- PWA血統モーダル Draft [#2643](https://github.com/yukki0113/GPT/pull/2643) は別の表示候補。未承認公開・デプロイ禁止。
- GitHub `main` が source/docs/tests/schema 正本。private M7実馬データ、private出力、鍵、秘密情報をpublic Git、Issue、Actions artifactに入れない。
- JRDB既存parserと `tools/data-storage/` を再実装しない。GitHub operationはルート `.gpt/GITHUB_OPERATION_POLICY.md` に従う。
- 本書は**将来の開発優先順位と合格条件の更新**であり、過去の監査実績・固定値・契約・承認状態を書き換えるものではない。

## 7. 次期開発優先順位

1. **新馬戦データ適格性監査**：JRA/JRDBのレース区分、初出走定義、父産駒/近親初戦の時点安全な抽出可能性、重複・欠損と実数を確認する。必要なら先に専用candidate schemaを作る。
2. **非採点のデビュー向け全頭レビュー候補**：既存①〜④データ基盤を再利用して、全出走馬について初戦条件の記述根拠と`NO_SAMPLE`を返す。通常レース向けcondition統計と混同しない。
3. **科学的検証の設計と固定**：既走馬の増分検証と新馬戦独立検証。騎手DBの契約を確認し、2DBの重複を測る。
4. **研究用RaceNote比較アダプタ**：本番のスコア・印・自信度・新聞を触らず、実際の新馬戦/既走馬を同一時点で検証する。
5. **昇格判断**：M6/M7の既存ゲート、consumer契約、文言/実機確認、明示的な本番承認を得た範囲だけをリリース。

重要：上記は目的上の優先順位であり、既存の未完了M7受入や他の並走タスクを自動中断・上書きしない。
