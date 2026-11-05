# BRDB 工程② — 12候補の種牡馬個体・祖先経路の外部ソース登録

Date: 2026-11-05  
Status: **RESEARCH SEED REGISTERED / SOURCE-NATIVE JBIS IDs / JRDB PERSON CROSSWALK UNRESOLVED / NOT HISTORICALLY AS-OF CERTIFIED**

## 1. 実施範囲

6工程の②「12候補の祖先情報登録」の**確認できる範囲の研究用登録**を実施。

- 種牡馬12頭のJBIS個別プロフィールと、**JBIS側固有ID**を特定。JRDBの8桁`horse_id`は12頭とも未対応（`null`）。
- 各プロフィールの直接の父`S`・母`D`の名前を**24件**観測記録。
- 祖父母の`SS`・`SD`・`DS`・`DD`の名前を**48件**、役割・経路と原出典付きで保持。
- 12候補のうち **Sunday Silence→Halo `S`** は、両者のJBIS個別IDを確認した外部IDリンクとして**1件のみ**記録。
- 残る23件の直接親の表示名と48件の祖父母名は**人物ID未確認**。祖先の血の不存在・合致・クロスを示す情報ではない。
- 個別馬の`lineage_code`は別のJRDB研究資料の**名前完全一致観測値**として併記。JBIS ID→JRDB horse_idや個体→公式系統コードの確定crosswalkではない。
- 国ルーツ4分類は維持しつつ**この登録からは自動付与しない**。成績適性の検証・加点も未実施。

### 登録正本

- `taxonomy/stallion_master_stage2_external_profiles_v0_1.json`: 出典付き12プロフィール・24親名・48祖父母名・1外部IDリンク。
- `src/brdb_stage2_master_registry.py`: 名寄せ禁止、親経路、分類未承認、本番未接続を検証するvalidator。
- `tests/test_brdb_stage2_master_registry.py`: 合成改ざん・誤昇格・欠損・経路混同の回帰テスト。
- [種牡馬マスタ設計](BRDB_STALLION_FEATURE_MASTER_DESIGN_V0_1_20261105.md) / [祖先ID不足の監査](BRDB_D2_12_ANCESTOR_ID_PATH_COVERAGE_AUDIT_20261105.md)。

## 2. 12種牡馬と個別ページの確認結果

外部IDは**すべてJBISのsource-native 10桁識別子**。数字が8桁のJRDB `horse_id`とは別物であり、推測して相互変換しない。

| 候補 | JBIS出典 | 外部識別子 | 生年 | JRDB系統コード | JBIS直接父母名 |
|---|---|---|---:|---|---|
| STORM_CAT | [Storm Cat](https://www.jbis.jp/horse/0000337102/) | `JBIS:0000337102` | 1983 | 1108（観測） | S:Storm Bird / D:Terlingua |
| TONY_BIN | [Tony Bin](https://www.jbis.jp/horse/0000161740/) | `JBIS:0000161740` | 1983 | 1307（観測） | S:Kampala / D:Severn Bridge |
| DANZIG | [Danzig](https://www.jbis.jp/horse/0000336082/) | `JBIS:0000336082` | 1977 | 1106（観測） | S:Northern Dancer / D:Pas de Nom |
| SADLERS_WELLS | [Sadler's Wells](https://www.jbis.jp/horse/0000336572/) | `JBIS:0000336572` | 1981 | 1109（観測） | S:Northern Dancer / D:Fairy Bridge |
| KINGMAMBO | [Kingmambo](https://www.jbis.jp/horse/0000347989/) | `JBIS:0000347989` | 1990 | 1503（観測） | S:Mr. Prospector / D:Miesque |
| ROBERTO | [Roberto](https://www.jbis.jp/horse/0000335167/) | `JBIS:0000335167` | 1969 | 1207（観測） | S:Hail to Reason / D:Bramalea |
| A_P_INDY | [A.P. Indy](https://www.jbis.jp/horse/0000339653/) | `JBIS:0000339653` | 1989 | 1311（観測） | S:Seattle Slew / D:Weekend Surprise |
| DEPUTY_MINISTER | [Deputy Minister](https://www.jbis.jp/horse/0000338072/) | `JBIS:0000338072` | 1979 | 1103（観測） | S:Vice Regent / D:Mint Copy |
| NORTHERN_TASTE | [Northern Taste](https://www.jbis.jp/horse/0000333544/) | `JBIS:0000333544` | 1971 | 1105（観測） | S:Northern Dancer / D:Lady Victoria |
| FORTY_NINER | [Forty Niner](https://www.jbis.jp/horse/0000337550/) | `JBIS:0000337550` | 1985 | 1503（観測） | S:Mr. Prospector / D:File |
| HALO | [Halo](https://www.jbis.jp/horse/0000335154/) | `JBIS:0000335154` | 1969 | 1206（観測） | S:Hail to Reason / D:Cosmah |
| SUNDAY_SILENCE | [Sunday Silence](https://www.jbis.jp/horse/0000333862/) | `JBIS:0000333862` | 1986 | 1206（観測） | S:Halo / D:Wishing Well |

- **JBISで直接確認した個別馬の同一性・父母名**と、**JRDB血統マスターで観測された日本語名称×公式コード**は別の根拠である。
- 研究資料の参照世代 `5279af0bd8226cde` では、12候補の旧祖先が独立した`pedigree_fact.horse_id`に収録されていない。したがって、JBISの外部人物IDを得たことによって旧祖先のJRDB IDが生まれたわけではない。
- JBISプロフィールの閲覧結果は2026年11月時点の確認であり、各歴史的レース日の前に同じ情報が参照可能だったかは未検証。`AS_OF_UNVERIFIED`を維持。
- 本実装はプロフィール画面で確認した必要最小限の血統関係のみ手作業で整理。JBISサイトの大量複製・生HTMLのGitHub転載はしない。外部情報の利用条件・出典は運用前に監査。

## 3. 祖先経路の扱い

- **個別馬内部での祖先表記**：`S`=父、`D`=母、`SS`=父父、`SD`=父母、`DS`=母父、`DD`=母母。
- **出走馬の父がこの種牡馬だと独立に確認された場合**：対象種牡馬内部の`p`は`S+p`へ展開。母父だと独立確認された場合は`DS+p`へ展開。
- ただし現在登録済みの`S/D/SS/SD/DS/DD`の大半は**名前による観測経路**。`person_id_verified=false`または`ancestor_external_id=null`の行は、血統クロス検出など「同一人物ID」前提の処理へ渡さない。
- **確定した外部IDリンクはSunday Silence→Haloの`S`だけ**。同一系統コードがあることや同じ表示名が別ページに登場したことだけで外部IDリンクを作らない。
- 母母`DD`の名前は今回の12頭の自己プロフィールとして観測できるが、出走馬の**母母ラインを取得したわけではない**。後続の工程④と分離。

## 4. バリデーション・再現

```bash
python horse-racing/brdb/src/brdb_stage2_master_registry.py \
  --registry horse-racing/brdb/taxonomy/stallion_master_stage2_external_profiles_v0_1.json \
  --shortlist horse-racing/brdb/taxonomy/embedded_blood_research_shortlist_candidate_v0_2.json \
  --observations horse-racing/brdb/taxonomy/jrdb_lineage_ancestor_observation_candidate_v0_1.json

python -m unittest discover -s horse-racing/brdb/tests \
  -p test_brdb_stage2_master_registry.py -v
```

期待集計：
```json
{
  "status": "STAGE2_RESEARCH_SEED_VALID",
  "subject_profiles_verified": 12,
  "parent_name_observations": 24,
  "second_generation_name_observations": 48,
  "verified_external_direct_paths": 1,
  "jrdb_identity_crosswalks": 0,
  "review_safe": false
}
```

**D1/2と同様、本書はGitHub正本の登録と読み戻しを確認した段階。Pythonテストの実行結果は実際に検証するまでPASS表記をしない。**

## 5. 残課題と工程③への引継ぎ

1. 12頭の個別JBIS IDを登録できたが、**現在の出走馬の父・母父との確定的なperson crosswalkはまだ無い**。①〜③の基礎統計は従来のJRDBコードと名前観測で続行可能だが、⑦の個体祖先一致とは区別。
2. 種牡馬マスタに多数の「出走馬の父」「出走馬の母父」を収録し、個体同一性・生年・公式系統コードを独立にguardした上で`S+`/`DS+`経路の展開coverageを測る必要がある。
3. 出走馬の父・母父から未確認の祖先名経路をたどって**検証済みの血統クロスを生成しない**。
4. 将来のsource rev/信頼できるID辞書と過去時点が確保できたときのみpath/region/条件適性statusを昇格。未確認はUNKNOWNのまま。
5. **①〜③ ＞ ④ ≫ ⑥⑦**を維持。⑤の新schema、BRDB CURRENT、凍結Review v0.1、RaceNote、PWA、新聞、既存workflowは更新しない。

## 6. ステータスまとめ

**工程②で確定したもの**：12頭のJBIS個別IDと情報源、24直接親名、48祖父母名と経路、1本の外部ID基準の直接父系リンク。

**工程②で未解決のもの**：JRDB個体IDへの連結、残りの祖先ID、歴史的な利用可能時点、実レースの含有coverage、地域型、血統適性。未解決を「非該当0件」としない。
