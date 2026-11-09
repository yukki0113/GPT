# P0 パック収録・解放キー候補ソース小規模監査（2026-11-09）

## 1. Scope and evidence

- Baseline: `docs/PACK_UNLOCK_NAVIGATION_P0_20261109.md`; fixed card-screen sample **30/30** already completed independently.
- **Three** Game8 secret-pack detail pages were inspected as individual browser-readable webpages. This is a small feasibility check, **not** automated crawling or licensed bulk extraction.
- Candidate sources:
  1. [無崩無窮の拳境](https://game8.jp/yugioh-masterduel/804857), article timestamp on inspected page **2026-08-06**.
  2. [新たな宇宙の仲間たち](https://game8.jp/yugioh-masterduel/425973), timestamp **2026-07-28**.
  3. [世界を覆う魔の力](https://game8.jp/yugioh-masterduel/425916), timestamp **2026-07-27**.
- Source-level unlock rule: [シークレットパック一覧と解放条件](https://game8.jp/yugioh-masterduel/424875), search snippet observed to report update **2026-10-26**; a different historical crawl of the same URL showed an older date. Preserve **observed article version / fetch context**; don't claim a single snapshot date without capturing bytes.

## 2. Three-page factual findings

| Pack | Rarity-grouped card list | Separate UR/SR unlock-key table | Current in-game pickup match | Current shop status |
|---|---|---|---|---|
| 無崩無窮の拳境 | YES: UR/SR/R/N text names | Heading present, cells **empty in extracted text** | NOT_CHECKED | UNKNOWN |
| 新たな宇宙の仲間たち | YES: UR/SR/R/N text names | Heading present, cells **empty in extracted text** | NOT_CHECKED | UNKNOWN |
| 世界を覆う魔の力 | YES: UR/SR/R/N text names | Heading present, cells **empty in extracted text** | NOT_CHECKED | UNKNOWN |

All **3/3** pages have a stable-looking section of explicit Japanese card names under rarity headings in the page's readable content; **3/3** unlock tables have no machine-readable card entries in the retrieved text. Blank content is **not** evidence that no key cards exist. The three URLs are source references only; **full card lists and page content are not copied to public Git**.

The source says a pack unlocks by acquiring a **pickup SR or UR** from generation or pack, ordinarily for 24 hours. The older individual pages state this generic condition. The newer `無崩無窮の拳境` page explicitly describes the named theme as pickup. Thus the working relation `rarity in {SR,UR} AND detail-page rarity list -> unlock candidate` is **plausible**, but remains `CANDIDATE`, **not confirmed for every listed card**. Future special rules and reprint changes may invalidate assumptions. No card was crafted or pack opened in this audit.

## 3. Usage conditions and blocker

- [Game8 robots.txt](https://game8.jp/robots.txt) explicitly `Disallow: /` for **GPTBot** and **dotbot**; do not equate all user agents or browser-readable pages with permission to run a bulk crawler.
- [Game8 terms](https://game8.jp/terms), **Article 7(2)** limits content utilization beyond normal viewing, including copying/reproduction; Article 7(1) reserves intellectual-property rights. No license allowing systematic capture/reuse as a persistent pack/card DB was identified.
- Interpretation: source browsing for a limited feasibility study occurred; **bulk automated crawling / local or Git mirror / persistent third-party-derived card-list dataset = NO-GO pending appropriate permission and permitted acquisition route**. This is operational risk classification, not a categorical assertion about every possible statutory exception or license.
- If licensed access proves unavailable, seek permitted alternate card/pack data, metadata offered under compatible terms, or independently recorded game observations with their own limits. Do not bypass robots, anti-bot walls or request authenticated secrets.

## 4. Consequences for technical design

- `pack_cards`: `source_article`, `observed_at`, `published_or_updated_at`, `pool_role=PICKUP_CANDIDATE`, `verification_status=CANDIDATE`, `source_rights_status=UNRESOLVED`. Do not automatically label as verified `PICKUP`.
- `pack_unlock_candidates`: derive candidates from **SR/UR** rows only *when acquisition and reuse of source data are permitted*. Mark `reason=SOURCE_DECLARED_PICKUP_SR_UR_RULE` and `key_status=CANDIDATE`; distinguish from `ACTIVATION_CONFIRMED`.
- `packs`: `shop_sale_status=UNKNOWN` until game- or other authorized time-stamped evidence. `locked_for_user` does not imply `sale_ended`.
- Card name crosswalk to canonical ID must normalize variants and flag ambiguous/nonmatches rather than auto-match silently. No complete page-to-card join was executed.
- The recorded 3/3 text-readable format does **not** guarantee stable DOM, rate limits, pagination, future page availability or rights.

## 5. P0 / P1 decision

| Gate | Outcome |
|---|---|
| Representative pages show textual rarity-scoped card listings | **PASS for 3 individual reads** |
| Separate per-card key-list text reliably retrievable | **NOT PROVEN (0/3 populated)** |
| Rule supports SR/UR pickup key-candidate derivation | **CONDITIONAL DESIGN SUPPORT** |
| Current official game pickup / live sales / exception matching | **UNVERIFIED** |
| Game8 automated extraction + persistent dataset reuse permission | **NO-GO / UNRESOLVED** |
| Bulk pack import or P1-A1 real-data full-text implementation | **NO-GO; NOT STARTED** |

## 6. Next bounded task

Research compliant alternative source(s) for pack↔card membership and explicitly usable licenses. If none, seek permission for systematic data ingestion or use a small manually verified observation ledger subject to data rights; avoid coercing user to screenshot the entire catalogue. Separately, synthetic fixtures can validate deck→pack→key ranking without storing real Game8 lists.

Do not claim that 30/30 card screen audit implies pack mapping 30/30 or that these three webpages demonstrate full-game pack coverage.
