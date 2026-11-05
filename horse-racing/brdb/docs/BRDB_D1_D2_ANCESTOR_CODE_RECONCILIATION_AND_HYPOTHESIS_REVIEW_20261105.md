# BRDB ⑥⑦ — JRDB系統対応監査と内包血統検証条件の精査 v0.1

Date: 2026-11-05  
Status: **VERIFIED OFFICIAL CODE FACTS + EXACT-NAME OBSERVATIONS / HYPOTHESIS SHORTLIST FOR REVIEW / NOT AN APPROVED PERSON-ID CROSSWALK / NOT PRODUCTION**.

## 0. 決定事項

- 地域ルーツは既存の `JP_RACING` / `US_RACING` / `EU_RACING` / `SOUTHERN_HEMISPHERE_RACING` を維持。出生国と同義にしない。
- **系統分類の正本はJRDBの大系統・小系統コード**。独自に「サンデー系」などの第三の公式コードを作らない。
- `sire_line_code`/ `broodmare_sire_line_code` は種牡馬の属する**系統**。特定の祖先そのものの `horse_id`、母父が特定の馬であること、地域型、同じ血を何代前に持つか、を**保証しない**。
- ①〜③ ＞ ④ ≫ ⑥⑦を保持。⑥⑦は⑤の `supplemental_insights` に限定し、未検証仮説を好材料へ自動加点しない。

## 1. 実際のJRDBコード確認

現地検証資産: `issue2223_research_generation_v02_5279af0bd8226cde_20261030.zip` の `generation/lineage_code_master.parquet`（SHA-256 `6263f4b239e9018e03fe6ce8333ba843b05c2eac32470369368e7be0fe7bd54b`）。manifest の固定SHAに一致し、**83個のJRDB公式系統レコード**を取得できた。形式は `lineage_code, major_code, major_name, minor_name, source_name, source_version`。source `JRDB code__keito`、version `2003-05-15`。

JRDB提供元の[系統コード表](https://jrdb.com/data_introduction/keito_code.html)とも代表コードを照合。完全な83レコードのコピーを新規taxonomy正本として作らず、BRDBの現行`lineage_code_master.parquet`を使い続ける。

| code | JRDB公式の小系統 | 区別すべき特定祖先 |
|---|---|---|
| 1103 | ヴァイスリージェント系 | デピュティミニスター |
| 1105 | ノーザンテースト系 | ノーザンテースト |
| 1106 | ダンジグ系 | Danzig |
| 1108 | ストームバード系 | **Storm Catではない** |
| 1109 | サドラーズウェルズ系 | Sadler's Wells |
| 1206 | ヘイロー系 | Halo、サンデーサイレンス（両者同一視禁止） |
| 1207 | ロベルト系 | Roberto、ブライアンズタイム（区別） |
| 1307 | ゼダーン系 | トニービン |
| 1311 | シアトルスルー系 | Seattle Slew、A.P. Indy（区別） |
| 1503 | ミスタープロスペクター系 | Kingmambo、Forty Niner（区別） |

## 2. 馬名と系統コードの観測照合（承認済み祖先IDではない）

`generation/pedigree_fact.parquet`（SHA-256 `1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536`）の`sire_name`または`broodmare_sire_name`に完全一致するラベルを条件に`GROUP BY code`。これらは**血統factの観測行数**であり競走出走数でも個別祖先へのcanonical-ID付与結果でもない。

| 表示名 | 父ラベル出現→code | 母父ラベル出現→code | 備考 |
|---|---|---|---|
| ヘイロー | 6→1206 | 167→1206 | 1206全体はHalo本人ではない |
| ストームキャット | 37→1108 | 773→1108 | 1108はStorm Bird系 |
| トニービン | 511→1307 | 1,938→1307 | 1307はゼダーン系 |
| ダンジグ | 24→1106 | 654→1106 | 1106はダンジグ系 |
| サドラーズウェルズ | 23→1109 | 848→1109、1→1107 | **例外行1件の監査が必要** |
| ミスタープロスペクター | 9→1501、2→1503 | 188→1501、286→1503 | **複数コードが観測**。統合しない |

13表示ラベルを [観測照合辞書](../taxonomy/jrdb_lineage_ancestor_observation_candidate_v0_1.json) に保存。各ラベルの `canonical_ancestor_id=null`、`approved_mapping=false` は維持。

**対応付けの2段階:**
1. `lineage_code -> official major/minor name`: 上記マスターで検証済み（**分類事実**）。
2. `target bloodline person -> canonical ancestor horse_id -> actual S/D path`: **未検証**（D2が要求するID経路）。馬名の一致だけではIDを採番・対応づけしない。

両者の対応は`code_observation`に留める。競馬文化圏（日本型・米国型等）は依然`CANDIDATE`で、公式コードを地域タグへ直変換しない。

## 3. 内包血統の対象は「4種だけ」より「12候補から段階的に検証」が適切

独自性・実測可能性・①②③との重複回避から、`embedded_blood_research_shortlist_candidate_v0_2.json` に**優先6 / 次点6**を記録。**いずれも採用確定・適性確認ではない。**

| 優先 | 個別祖先 | 最初に検証したい差 | 留意点 |
|---|---|---|---|
| A | Storm Cat | 母方での配置×ダート/芝・距離 | Storm Bird系と個別馬を混同しない |
| A | トニービン | 母方での配置×東京芝・距離 | 左回り等はコース定義後 |
| A | Danzig | 母方での配置×芝短距離/マイル・道悪 | Danzig系の全馬を代入しない |
| A | Sadler's Wells | 母方での配置×芝中長距離・道悪 | sourceコード例外を監査 |
| A | Kingmambo | 母方での配置×芝ダ/距離 | 母父系1503だけではKingmambo同定不可 |
| A | Roberto | 母方での配置×芝ダ/距離・馬場 | ロベルト系と個別祖先を区別 |
| B | A.P. Indy | 母方×ダート距離帯 | Seattle Slew系との重複 |
| B | Deputy Minister | 母方×ダート短中距離 | Vice Regent系全体と別 |
| B | Northern Taste | 母方×芝・競馬場 | 世代・時代の偏りに注意 |
| B | Forty Niner | 母方×ダート短距離 | Kingmamboと同じ1503でも祖先は別 |
| B | Halo | 母父`DS`と遠祖で条件を分ける | 現役馬で直接母父Haloは希少 |
| B | Sunday Silence | 母父`DS`とその他経路、芝条件 | ①②③との重複が大きい |

**血統配置は少なくとも** `DS`（母父そのもの）、`D*`（その他の母方祖先）、`S*`（父方祖先）、同一IDのcrossを分離し、可能なら2代/3代/4–5代も層化。すべてを`contains=YES`でまとめることは禁止。

HaloとSunday Silenceをともに候補としたのは、`1206`に含まれる別個の人物であることを明確にしたかったためで、無条件に両者を独立な好材料として数えない。

## 4. 検証する条件の優先順位とデータの可用性

JRDB Analysis v1.4 `fact_entry_result_lite` の実Parquet（2016年分）で次の**原列の存在**を確認:
`race_date, venue_code, track_type, distance, track_condition_code, course_code, race_condition_code, grade_code, frame_no, age, finish, abnormal_code, final_win_odds, final_win_popularity` 等。

| 優先 | 検証軸 | 理由・検証条件 |
|---|---|---|
| P1 | 芝/ダート × 距離帯（必要なら距離） | ①〜③の正本条件と一致、比べやすい |
| P1 | 競馬場 × 芝/ダ × 距離帯 | 想定舞台に直接対応。細分しすぎなら母数不足を明示 |
| P2 | 馬場状態（良/稍重/重/不良）を**芝・ダート別**に比較 | `track_condition_code` 原列あり。**公式コードの解釈、芝/ダとの整合、時点を先に検証**。道悪と高速時計を同一視しない |
| P2 | コース形状・左右・坂 | `course_code` 原列あり。ただし公式コース対応辞書を別に確認するまで「中山＝常に小回り」の固定推定は禁止 |
| P3 | 距離短縮/延長、芝↔ダ切替 | 対象馬の前走を時系列で接続し、出走選択バイアスを考慮 |
| P3 | 2歳・3歳前半・古馬などの年齢 | `age`あり。ただし世代差・成長差・開催時期を考慮 |
| 保留 | 内枠、脚質、初速、ピッチ走法、スタミナなど | `frame_no`や`running_style`だけで遺伝的形質を証明できない。直接観測項目と条件を決めてから |

分析集団ごとに `unique_horses`/ `starts`/ `wins`/ `top3`/ baselines/信頼区間と、血統経路coverage、前提となる当時公開時点・父個体や母父個体による重複を記録。**人気差補正が可能か**は `final_win_odds` / `final_win_popularity` と**予想時点オッズの区別**を守り、結果確定後オッズを事前特徴に流用しない。

## 5. D3の開始前に残る確認

1. D2祖先グラフの`horse_id`経路で各候補の**実在する個体ID**を独立同定。異表記・別国表記は正規aliasと照合。名前に一致しただけでは採用禁止。
2. `サドラーズウェルズ`・`ミスタープロスペクター`の異なる系統コード観測行の由来を監査。命名の揺れか系統コード不整合かは未判定。
3. `track_condition_code`の公式コード定義を確定し、芝とダートで同じラベルが同じ意味かを検証。
4. コース形状辞書を別に作り、場名だけで小回り・左回りを断定しない。
5. 候補別に祖先IDの現行coverageを測り、十分な観測数がない仮説は`DEFERRED_LOW_COVERAGE`にする。
6. 仮説選択期間と検証期間は分離、複数検定と①〜③への**追加説明価値**を記録。
7. 将来の⑥⑦追加コメントは1〜2件程度、⑤主結論への加点/上書きなし。

## 6. 変更境界

本書と2つの研究用候補JSONのみを追加/更新する。従来のD1候補辞書、D2位置検出エンジン、⑤schema、Blood Review v0.1、BRDB CURRENT、RaceNote、PWA/新聞の本番挙動は変更しない。

**次の実装にあたり、A/Bの候補数・条件軸はユーザーのレビューを経て確定する。**
