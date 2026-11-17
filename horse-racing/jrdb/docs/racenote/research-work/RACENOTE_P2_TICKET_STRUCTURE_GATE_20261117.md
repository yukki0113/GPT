# RaceNote P2 v0.1 — 印外リスク・同時好走・買い目構造の事前著述契約

Date: 2026-11-17
Status: **RESEARCH PRE-FREEZE GATE IMPLEMENTED / NO NEW RACE DECISIONS AUTHORED**

## 1. 研究目的

馬券を当て、継続的なプラス収支を目指す。既存RaceNote v0.5.6の◎○▲△△は据え置き、A/B/Cではなく、**3着内候補の印外漏れ・印内2頭/3頭の同時好走・券種/点数**を分離する。

根拠: [20261117_RACENOTE_P1_FAILURE_AUDIT_AND_P2_TICKET_DESIGN.md](./reports/20261117_RACENOTE_P1_FAILURE_AUDIT_AND_P2_TICKET_DESIGN.md)。

本版は**予測を自動生成する仕組みではない**。LLMがReader全頭を読み、馬ごとの実走情報と条件を判断・著述する。決定論的Pythonは、作成済み判断の網羅性・根拠参照の有効性・既存Freezeとの一致を検査するだけ。

**2025年の既検証156Rは設計用データ**。P2の新しいブラインド検証の成績として流用しない。

## 2. Gate 1：印5頭＋印外の全出走馬を点検

Readerの全出走馬を網羅し、凍結印5頭それぞれの \`five_roles\` と、印外全頭の \`outside_screen\` を独立に著述。

- \`five_roles\`: 各馬につき \`win_path\` / \`top2_path\` / \`top3_path\` / \`failure_path\` と \`evidence_refs\`。
- \`outside_screen\`: 印外全頭の馬番・分類（\`THREAT\` / \`MONITOR\` / \`LOW\` / \`INSUFFICIENT_EVIDENCE\`）、具体的3着内経路、Reader証拠。
- \`outside_summary\`: 印外脅威が印5頭の捕捉能力をどう妨げるか。分類の数だけを使って自動PASSしない。
- 印の序列だけで馬券内役割を割り当てない。馬番の入替えだけのテンプレートも不可。

\`evidence_refs\` は現物Reader内のJSON Pointer（例 \`/horses/0/evidence/ABILITY/P/idm\`）で、該当馬の値を直接指す。配列内の \`0\` は馬番でなく**Readerのhorses配列インデックス**。根拠が無い項目を捏造しない。

## 3. Gate 2：同時好走の具体例を組み立てる

\`cooccurrence_cases\` は候補となる**印内**2頭または3頭の組み合わせについて、券種ごとに次を記録する。

- \`case_id\`: 1開催日内の1Rで重複しないID。
- \`bet_type\`: \`WIDE\`（2頭とも3着内）、\`QUINELLA\`（2頭とも2着内）、\`TRIO\`（3頭とも3着内）。
- \`horse_nos\`: 馬番昇順、重複なし。
- \`shared_scenario\`: 全馬が同時に好走する展開と各馬の位置取り。
- \`conflict_scenario\`: ペース競合、脚質依存、差し損ね等、同時好走が破綻する具体例。
- \`evidence_refs\`: その組み合わせの**全馬分**の実在Reader根拠。

\`cooccurrence_cases\` に候補があっても強制購入しない。\`PASS\` は正当な判断。

## 4. Gate 3：馬券の固定（市場非参照・構造実験）

\`purchase_decision\` は \`PROVISIONAL_BET\` または \`PASS\`。

- \`PROVISIONAL_BET\`: \`tickets\` に事前に著述した券種・具体馬番・紐付く \`case_id\`・1点100円を記録。1レース最大12点・1,200円。
- \`PASS\`: \`tickets=[]\`、\`no_bet_reason\` に個別の理由。
- \`market_available=false\` を必須。今回のコードはオッズ・人気・確定結果を参照しない。**PROVISIONAL_BETは実際の投資推奨・正の期待値を意味しない。**
- 市場オッズによる配当採算・期待値判断は今後の別ゲート。元データでの時点保証なしに後日の最終オッズを混ぜない。
- 同時好走確率は独立勝率の掛け算で作らない。確率を未較正のまま数値化させない。

## 5. Input JSON envelope

入力JSONは次の構造。実際の \`records\` には凍結済み全Rを入れる。次は**構造の例**であり、実在馬の予想ではない。

\`\`\`json
{
  "schema_version": "racenote-p2-ticket-structure-v0.1",
  "selection_id": "BTDAY-XXXX",
  "target_date": "YYYY-MM-DD",
  "result_opened": false,
  "target_market_opened": false,
  "confidence_used": false,
  "records": [
    {
      "venue": "東京",
      "race_no": 1,
      "marks": [1, 2, 3, 4, 5],
      "reader_sha256": "<frozen Reader SHA256>",
      "decision_core_sha256": "<frozen Decision Core SHA256>",
      "five_roles": [
        {
          "horse_no": 1,
          "win_path": "<Readerに基づく勝利経路>",
          "top2_path": "<連対までの条件>",
          "top3_path": "<3着内に残れる条件>",
          "failure_path": "<この馬の着外経路>",
          "evidence_refs": ["/horses/0/evidence/ABILITY/P/idm"]
        }
      ],
      "outside_screen": [
        {
          "horse_no": 6,
          "classification": "THREAT",
          "top3_path": "<印外6番の具体的割込み経路>",
          "evidence_refs": ["/horses/5/evidence/ABILITY/P/idm"]
        }
      ],
      "outside_summary": "<全印外馬の脅威と捕捉不確実性>",
      "cooccurrence_cases": [
        {
          "case_id": "wide_1_2",
          "horse_nos": [1, 2],
          "bet_type": "WIDE",
          "shared_scenario": "<1と2が同時に3着内に入る展開>",
          "conflict_scenario": "<1と2が同時に凡走する展開>",
          "evidence_refs": [
            "/horses/0/evidence/ABILITY/P/idm",
            "/horses/1/evidence/ABILITY/P/idm"
          ]
        }
      ],
      "purchase_decision": "PROVISIONAL_BET",
      "tickets": [
        {
          "bet_type": "WIDE",
          "horse_nos": [1, 2],
          "stake_yen": 100,
          "case_id": "wide_1_2"
        }
      ],
      "no_bet_reason": null,
      "market_available": false
    }
  ]
}
\`\`\`

ここでは \`five_roles\` の他4頭と \`outside_screen\` の全馬を省略しているため、**この例自体はGateにPASSしない**。予想の文章を水増しするのではなく、実際の全頭Readerを検討する必要がある。

## 6. 検証・研究用Freezeコマンド

GitHub \`main\` の最新4種を使用：

\`\`\`bash
python horse-racing/jrdb/src/racenote_p2_ticket_gate.py \
  --root horse-racing/jrdb/backtests/BTDAY-XXXX/YYYYMMDD/v056 \
  --draft /path/to/p2_authored_full_day.json
\`\`\`

全R、印、SHA、Reader実ファイル、証拠Pointer、具体的組合せ、点数、結果未参照を検証し、\`status=PASS\` の場合のみ研究用Freeze：

\`\`\`bash
python horse-racing/jrdb/src/racenote_p2_ticket_gate.py \
  --root horse-racing/jrdb/backtests/BTDAY-XXXX/YYYYMMDD/v056 \
  --draft /path/to/p2_authored_full_day.json \
  --freeze-output /path/to/research-work/p2_frozen_BTDAY-XXXX.json
\`\`\`

Freezeは既存v056の外部パスのみに新規書込（上書き禁止）。**このCLIが作るのはローカルファイル**であり、GitHub正本への記録は別途コミット＋読み戻し＋照合が必要。既存Prediction/Confidenceを上書きしない。

成果物のResearch Freezeには、完整な著述内容、著述ファイルSHA、元Prediction SHA、Reader Manifest SHA、品質監査を含む。

## 7. Gateの限界と次の実行

- ゲートはReader Pointerの存在と馬番一致を検査するが、**根拠文の競馬的妥当性・本当に全頭の比較を考え抜いたか・過去結果の知識が意味的に混入していないかは機械では証明できない**。
- 初めて使う新規対象では、以前の結果照会済み日を混ぜて正式な初回評価としない。日付再利用の場合は \`cycle=2\` を明示する。
- 新しい結果未照会BTDAYで一日分のLLM著述を行い、Gate PASS→研究用Freeze→SHA確認→初めて決済結果を見る。
- 研究用途の事前比較はWIDE上位3頭BOX・馬連・3連複などを同一固定条件で設定。結果に応じて最良券種を後付け採用した場合は探索扱い。
