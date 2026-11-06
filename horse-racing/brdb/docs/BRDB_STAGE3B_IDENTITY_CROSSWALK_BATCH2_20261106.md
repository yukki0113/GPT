# BRDB ③-B：第2回JRDB⇔JBIS個体対応（高頻度3頭追加）

Date: 2026-11-06  
Status: **THREE MORE RESEARCH INDIVIDUALS MULTI-GUARD VERIFIED / 5 TOTAL / 29 OF 48 PRIORITY PATHS SOURCE-BRIDGED / NOT PRODUCTION**

## 概要

2022〜2024年生まれの研究用血統マスターを対象にした③-Bの高頻度上位50種牡馬研究ネットワークで、既存のディープインパクト・キングカメハメハ2頭に加え、**ダイワメジャー・ハーツクライ・エピファネイア**の3頭について、JRDB研究世代とJBIS個別馬プロフィールの外部source-native individual ID対応を確認した。

- JRDB研究世代: `5279af0bd8226cde`
- `pedigree_fact.parquet` SHA256: `1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536`
- 上位50研究JSON SHA256: `89d01e2c05af27a929c8398ef9e94660f5f1e442362d458383db6e6a9bd7bdc0`
- JBIS資料確認日: 2026-11-06。予想時点の情報可用性は`AS_OF_UNVERIFIED`。全て`prediction_safe=false`。

## 1. 追加3頭の多項目同定

| JRDB馬名 | JRDB ID | JBIS ID | 生年月日 | 父（生年） | 母（生年） | JRDB父系コード |
|---|---|---|---|---|---|---|
| ダイワメジャー | `01103114` | `0000725485` | 2001-04-08 | サンデーサイレンス（1986） | スカーレットブーケ（1988） | `1206` |
| ハーツクライ | `01103038` | `0000722158` | 2001-04-15 | サンデーサイレンス（1986） | アイリッシュダンス（1990） | `1206` |
| エピファネイア | `10104155` | `0001124297` | 2010-02-11 | シンボリクリスエス（1999） | シーザリオ（2002） | `1207` |

3頭の`horse_id`は実Parquetにそれぞれ1件のみ出現。JRDB側`horse_name, birth_date, sex_code, sire_name, sire_birth_year, dam_name, dam_birth_year, sire_line_code` を直接照合。JBISプロフィールで日本語名・完全生年月日・牡・父母名と父母生年を確認。JRA個別ページも氏名・誕生日・父母を照合できる独立した補足資料として残した。

**個別出典**：
- [JBIS：ダイワメジャー](https://www.jbis.or.jp/horse/0000725485/) / [JRA競走馬情報](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102001103114%2F35)
- [JBIS：ハーツクライ](https://www.jbis.or.jp/horse/0000722158/) / [JRA競走馬情報](https://sp.jra.jp/JRADB/accessU.html?CNAME=sj01ude102001103038%2F65)
- [JBIS：エピファネイア](https://www.jbis.or.jp/horse/0001124297/) / [JRAプロフィール](https://www.jra.go.jp/gallery/3minmeiba/horse27/index.html)

**系統コードはJRDB側の正本情報**であり、JBIS側で「1206」が承認されているという意味ではない。同一人物の対応と、海外の旧祖先本人がJRDBの8桁馬IDを持つかどうかは別問題。

## 2. 血統ネットワークの増分

追加3頭の既存出典照合済み経路は次の3本。

| 登録主体 | 内部パス | 外部祖先本人 |
|---|---|---|
| ダイワメジャー | `S` | `JBIS:0000333862` サンデーサイレンス |
| ハーツクライ | `S` | `JBIS:0000333862` サンデーサイレンス |
| エピファネイア | `DSS` | `JBIS:0000333862` サンデーサイレンス |

エピファネイアの`DSS`は「本人→母シーザリオ→母の父スペシャルウィーク→その父サンデーサイレンス」。`S`と同じ血統経路として統合してはならない。

| 指標 | 前バッチ | 今回 |
|---|---:|---:|
| 研究用本人JRDB⇔JBIS照合が完了した入口 | 2 | **5** |
| 既存優先4祖先の観測経路 | 48 | **48** |
| ハイブリッド外部祖先IDまで経路証拠が連続するもの | 26 | **29** |
| 続く本人同定が不足している経路 | 22 | **19** |
| 正式なJRDB旧祖先IDの追加 | 0 | **0** |

**29/48=60.42%**は、優先4祖先に関する子孫側のsource-bridge provenanceに限る。血統マスター全体の3代・5代カバー率でも、現役馬の父母父を正式IDで網羅した割合でもない。また今回は新たに子孫を推定経由で連鎖させて29を得たのではなく、**既存26件の完成済み監査＋元のpending22件から実際の3件を確認した増分**である。

## 3. 成果物・再現手順

- `taxonomy/stage3b_jrdb_jbis_crosswalk_research_v0_2.json`：以前の2個体に今回の3個体を追加。全5個体のsource URL・JRDB内の親事実・承認状態を保持。その他26個体は未認証。
- `src/brdb_stage3b_crosswalk_batch2_audit.py`：登録5個体、出典付き48経路、上位50研究データ、前回の26/22監査の整合を検証し、研究用増分を明示。出所が明らかでない連結を拒否。
- `src/run_brdb_stage3b_batch2_from_parquet.py`：immutable SHA確認後、DuckDBで5個体の元プロフィールを読み取る研究用エントリ。
- ローカル独立監査（正本モジュールとは別実装）で実Parquetから3件の同一性ガードを実行、先行pending22件との重複なしを確認し`26+3=29`、残り19を再計測。
- ローカル監査で**7件のPython unittestを実行し全件PASS**（役割パス違い、未解決候補との照合、ID一意性、SHA等）。ただしこの7件はローカル独立監査スクリプトに対するテストであり、**GitHub登録版のPythonモジュールを実行した証跡ではない**。現行の既存GitHubコード群の全回帰テストは未実行。

元データを持つ環境で再実行する場合：

```bash
python horse-racing/brdb/src/run_brdb_stage3b_batch2_from_parquet.py \
  --pedigree /path/to/generation/pedigree_fact.parquet \
  --registry horse-racing/brdb/taxonomy/stage3b_jrdb_jbis_crosswalk_research_v0_2.json \
  --bridge horse-racing/brdb/taxonomy/stage3b_priority4_bridge_candidate_v0_4.json \
  --top50 /path/to/stage3b_top50_master_research.json \
  --baseline /path/to/stage3b_hybrid_2crosswalk_26paths.json \
  --output /tmp/brdb_stage3b_batch2_audit.json
```

**禁止境界**：JBISの外部person IDをJRDB 8桁horse IDへ流用しない。馬名/生年だけの照合を自動承認しない。JRDB公式系統を血統上の個人IDや国ルーツと誤認しない。⑥⑦の条件適性・⑤の加点へ自動接続しない。過去時点の情報可用性が不明なまま実運用予想へ導入しない。

## 4. 次に同定する対象

残る19経路は、名前・血統位置とJBIS出典の紐付け自体は既にあるが、**途中の馬個体を確実に接続できていないもの**。次に候補はステイゴールド、ブラックタイド、スペシャルウィーク、オルフェーヴル、キタサンブラックなどの中間接続点を、登場頻度・祖先到達増分・出典整備容易性を合わせて選ぶ。

本番のBRDB CURRENT、Blood Review、RaceNote、PWA、新聞、Actions等は変更しない。
