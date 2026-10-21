# BRDB UKC Dam/BMS Inconsistency Audit 2026-10-21

Status: COMPLETE  
Date: 2026-10-21

## Objective

Audit the apparent inconsistencies found when:

1. a target horse's dam is resolved by exact `dam_name + dam_birth_year`, then
2. the target horse's `broodmare_sire_name + broodmare_sire_birth_year` is compared with
3. the resolved dam horse record's `sire_name + sire_birth_year`.

No fuzzy match or Web data is used.

## Reproduction correction

A clean rerun over the canonical Drive Raw archives `UKC_2010.zip` through `UKC_2025.zip` produced:

- 780,855 valid UKC observations
- 82,107 unique horses after latest-observation reduction
- 11,818 horses appearing in 2025 UKC
- 8,198 target horses whose dam resolved uniquely by exact name + birth year
- 8,097 exact dam/BMS key agreements
- 101 apparent inconsistencies

The earlier validation note reported 102 inconsistencies. That count was off by one. The reproducible value is **101**.

## Classification

Of the 101 apparent inconsistencies:

### A. Name spelling / transliteration only: 100

All 100 have:

- identical sire birth year
- identical JRDB lineage code
- different Japanese name spelling only

There are only 22 distinct name-pair variants behind the 100 rows.

Most frequent examples:

| target BMS spelling | resolved dam sire spelling | rows |
|---|---|---:|
| ロックオブジブラルタル | ロックオヴジブラルタル | 13 |
| モアザンレディ | モアザンレディー | 9 |
| ディストーテッドヒューマー | ディソーテッドユーモア | 9 |
| ハーランズホリデー | ハーランズホリデイ | 9 |
| スタチューオブリバティ | スタテューオブリバティ | 8 |
| スパイツタウン | スペイツタウン | 6 |
| キトゥンズジョイ | キッテンズジョイ | 6 |
| ヘンリーザナヴィゲーター | ヘンリーザナビゲーター | 6 |
| ダンシリ | ダンジリ | 5 |
| フォーティナイナーズサン | フォーティーナイナーズサン | 4 |

Other observed pairs include:

- ルロワデザニモー / ロルワデザニモー
- キャンディライド / キャンディーライド
- マジェスティックウォリアー / マジェッスティックウォリアー
- ブロークンヴァウ / ブロークンヴォウ
- アルデバラン２ / アルデバラン
- ルアーヴル / リアーヴル
- テイルオブザキャット / テイルオヴザキャット
- キャメロット / キャメロッ
- スターオブコジーン / スターオヴコジーン
- ホーリーローマンエンペラー / ホーリーローマンエンパイア
- デクラレーションオブウォー / デクレレーションオブウォー
- ソングアンドアプレイヤー / ソングアンドプレイヤー

### Historical spelling revision within the dam record

23 of the 100 spelling-only cases are directly explained by UKC history:

- an earlier observation of the dam used the same sire spelling as the target horse's BMS field;
- the latest observation of the dam later used a revised spelling.

Therefore these 23 are demonstrably temporal normalization/correction effects inside UKC itself.

The remaining 77 are still supported as spelling variants because:

- birth year is identical;
- lineage code is identical;
- the mismatch belongs to one of the repeated deterministic name-pair variants above.

BRDB should not treat these as pedigree contradictions.

## B. Genuine false parent resolution by name + birth year: 1

Target:

- horse_id: `22110095`
- horse_name: トーセンビギン
- dam_name: ヴィヴァルダ
- dam_birth_year: 2015
- broodmare sire: サウスデール (2006)
- broodmare-sire line code: 1503
- breeding place: 愛

Exact `ヴィヴァルダ + 2015` lookup in the JRDB horse master resolves to:

- horse_id: `15101582`
- horse_name: ヴィヴァルダ
- birth date: 2015-04-29
- sire: アンテロ (2010)
- sire line code: 1109
- breeder: ダーレー・ジャパン・ファーム
- breeding place: 日高

These are not the same mare.

Additional evidence:

Domestic offspring tied to JRDB horse_id `15101582`:

- ヴァイキングムーン — dam ヴィヴァルダ / BMS アンテロ
- ドレスメイカー — dam ヴィヴァルダ / BMS アンテロ
- ヴィヴィッドムーン — dam ヴィヴァルダ / BMS アンテロ

Foreign-bred offspring with another mare also rendered as `ヴィヴァルダ` born 2015:

- アリスバリー — BMS サウスデール / breeding place 愛
- トーセンビギン — BMS サウスデール / breeding place 愛

This proves that **parent name + birth year can collide across distinct horses**, especially foreign pedigree entities whose own canonical JRDB horse record is absent.

The false join is detectable here because both:

- BMS name/year disagree materially, and
- lineage code disagrees: 1503 vs 1109.

## Revised relation-resolution rule

BRDB must NOT accept a parent horse_id solely because `parent_name + parent_birth_year` produces one JRDB horse candidate.

For dam resolution, require consistency with the child's independently supplied BMS facts.

Recommended v0.1 rule:

```text
candidate = exact(dam_name, dam_birth_year)

accept candidate only if:
  candidate count == 1
  AND candidate.sire_birth_year == child.broodmare_sire_birth_year
  AND (
       candidate.sire_name == child.broodmare_sire_name
       OR approved JRDB-name-alias relation is established
      )
  AND candidate.sire_line_code == child.broodmare_sire_line_code
```

If any guard fails:

```text
relation_status = AMBIGUOUS_OR_CONFLICT
resolved_dam_horse_id = null
```

Do not guess.

## Alias handling

Do not use unconstrained fuzzy string matching.

Instead BRDB may derive a versioned JRDB pedigree-name alias table from observed, provenance-backed equivalences such as:

- same role relationship
- same birth year
- same lineage code
- repeated UKC evidence and/or historical correction evidence

Example semantic structure:

```text
pedigree_name_alias
  canonical_name
  observed_name
  birth_year
  lineage_code
  evidence_type
  evidence_count
  first_observed
  last_observed
  alias_version
```

The 22 pairs found in this audit are candidates for such a table, not an automatic permanent normalization list until frozen.

## Effect on previous match-rate finding

The first-generation exact-name+birth-year match rate remains useful as a candidate-generation rate.

However:

- `unique exact candidate` != `verified parent relation`
- candidate resolution needs cross-field consistency guards

For dams in the 2025 cohort:

- unique name+birth-year candidate: 8,198
- proven false collision from this audit: 1
- spelling-variant consistency cases: 100
- all remaining apparent contradictions resolved as name normalization except the one collision

Thus the relation technique remains strong, but must be guarded.

## Decision

PASS for use as a **candidate parent resolver**.

FAIL for use as an unconditional canonical parent resolver.

BRDB canonical rule:

1. generate candidate by exact parent name + birth year;
2. validate with independent pedigree facts when available;
3. resolve name aliases through a versioned explicit alias layer;
4. fail closed on cross-field conflict;
5. retain source/provenance and resolution status.
