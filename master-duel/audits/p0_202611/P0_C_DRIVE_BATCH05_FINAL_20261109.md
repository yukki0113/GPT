# P0-C Batch05: final priority 07 screenshot (2026-11-09)

## Evidence / procedures

- Drive `CardImage` folder ID `1muOvgXuFiolFkoKoKYByDgILAKHeD6J2` contained 30 PNGs, including one new `IMG_9794.PNG`, ID `1NLe_qTCoS12IcX16fTjkdQgdyFhBaw1j`, 1,044,796 bytes.
- Downloaded, viewed actual game UI and independently hashed the original: SHA-256 `34156378784a6314afee9e3e206b80b049438e92dc68a30953c5bd81c99ac6c7`.
- Renamed in Drive: `MD_アンデット・ウォーリアー_詳細.png`. GitHub stores **no screenshot binary, full copyrighted text or user personal inventory/CP**.
- MD JSON snapshot `master-duel-raw.json` lists English identity `Zombie Warrior`, rarity **N**, Japanese fusion material `ワイト` + `格闘戦士アルティメーター`. `cards.json` crosswalk connects `Zombie Warrior` to Japanese name `アンデット・ウォーリアー`, KONAMI ID **4036**. UI shows same name, fusion material, monster attributes (DARK / Zombie / Level 3 / ATK 1200 DEF 900) and N rarity.
- Screen shows **blue N CP30 generate** enabled for selected card edition; not executed. Screen shows **no explicit restriction icon**. This does **not** prove unrestricted allowed copies.
- An `入手方法` button is visible, **not opened**; existence of button is **not** a verification of pack or live shop inventory. `current.vector.json` dated 2026-11-05 has no entry for ID 4036; omission is not treated as dated unrestricted confirmation.

## Final 30-card visual scope

| Observation | Verified |
|---|---:|
| Sampled card identity and MD rarity | **30/30** |
| Effect / fusion material visually compared to MD snapshot | **30/30** (meaning-level, **not** bytewise text equality) |
| Selected artwork / edition craft button state | **30/30** (enabled **26**, disabled **4**) |
| Explicit banlist icon vs 2026-11-05 vector | **4/4**, only four screenshots with explicit markers |
| Acquisition-method screens | **2/30** (remaining 28 unverified) |
| Direct current live shop sales | **0/30** |

There are no remaining missing cards in the **fixed 30** visual audit sample. Drive folder's 30 names are all `MD_...` after rename. This closes **P0-C's specific 30-card identity/rarity/effect-visual sample collection**, *not* the overall P0 evaluation or source suitability gate.

## Outstanding / decision

- Screenshots are not official redistribution clearance, and unofficial card data rights remain unproven; **no** screenshot or raw Japanese card text is published to GitHub.
- The source's dated banlist vector must not be silently represented as today's game-mode/format-specific effective rules. "No marker" is **not** 3 unrestricted copies.
- Pack/acquisition screens and current shop sales were not covered by this sample, so don't infer actual availability or pack purchase capability.
- Selected artwork generation possibility and legal deck use are **separate dimensions** (forbidden Elpy was observed with active craft button).
- **P1-A1 real card catalog and effect full-text implementation: NO-GO remains**, pending P0 other checkpoints and data rights/operational specification. No P1 implementation performed.
