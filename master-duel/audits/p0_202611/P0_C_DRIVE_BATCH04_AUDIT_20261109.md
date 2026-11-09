# P0-C Batch04 — C追加4枚 (2026-11-09)

## Source and verification

- Drive `CardImage` folder `1muOvgXuFiolFkoKoKYByDgILAKHeD6J2` was re-listed after Batch03: the four previously missing files became visible. They are `IMG_9786.PNG`, `IMG_9787.PNG`, `IMG_9788.PNG`, `IMG_9791.PNG`. Source images were downloaded and visually identified before Drive rename, not inferred from file numbering.
- All four were renamed to `MD_<カード名>_詳細.png`. File ID and SHA-256 listed in [batch04 CSV](P0_C_DRIVE_BATCH04_4_IMAGES.csv). Original screenshot binary and copyrighted card text are kept out of public Git.
- Fixed 30-checklist priority rows: 14, 15, 16, 19. The existing first C sub-batch covers rows 17,18,20,30.
- Screenshot comparison against `master-duel-raw.json` Japanese text is **visual semantic comparison**, not exact character-by-character equality. JSON snapshot previously hash-verified; dated regulatory vector `2026-11-05` used only for explicitly marked item.

| Original | Card | MD rarity | Banlist marker | Selected edition craft |
|---|---|---|---|---|
| IMG_9786 | 守護竜エルピィ | UR | **⛔ forbidden 0** | UR CP30 enabled |
| IMG_9787 | ＥＭバブルドッグ | N | none visible | N CP30 enabled |
| IMG_9788 | アストログラフ・マジシャン | UR | none visible | UR CP30 enabled |
| IMG_9791 | 魔弾－デビルズ・ディール | N | none visible | N CP30 enabled |

- Name and MD rarity 4/4 visually match the crosswalk and MD candidate JSON. Japanese effects show no material semantic discrepancy in visual comparison (4/4, not a bytewise proof).
- **守護竜エルピィ** has explicit forbidden (⛔) marker, and the 2026-11-05 `current.vector.json` maps KONAMI ID **14128 to 0**, therefore **1/1 marked check agrees**. The screenshot does not establish official effective date or play mode. Its blue enabled generation button demonstrates **craft visibility is independent of forbidden deck legality**.
- Other three have no restriction marker visible. This does **not** establish unlimited allowed copies.
- All four selected editions show the blue craft button. No crafting performed. No separate acquisition method, pack availability or current shop screenshots were provided. Owned count and CP balance are excluded from public audit.

## C aggregate and P0 status

Batch03+04: **8 new unique cards**, all named and matched for rarity and visually reviewed effect. Across prior 21 cards, fixed P0-C progress is **29/30**. Selected edition craft UI also **29/30**: 25 enabled and 4 disabled. Explicit markers checked against dated vector **4/4** overall (three older plus Elpy). Acquisition 2/30; current-shop purchase direct checks 0/30.

**One missing fixed sample: priority 07 `アンデット・ウォーリアー` (fusion N), KONAMI ID 4036.** The other 29 are complete at the stated visual-review depth, not fully MD-official or pack-current validated. **P1-A1 real-card catalog/full-text index NO-GO continues**, with rights conditions, banlist revision date/mode and pack-current availability outstanding.
