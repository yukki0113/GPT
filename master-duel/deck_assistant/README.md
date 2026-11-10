# Master Duel: Private Deck Assistant (M1)

`deck_assistant` is a read-only, standalone query/assessment layer over the existing schema v1 SQLite extracted from the private production ZIP.

- `search_cards`: normalized Japanese card-name substring + exact kind/rarity/attribute.
- `search_effects`: **literal** Japanese text phrase AND matching, returning complete source text/version. **Not semantic effect search**.
- `resolve_names`: no guessing when normalized names are ambiguous.
- `assess_deck`: supplied recipe only; evaluate `STRICT_NO_UR`, `LOW_RARITY_CORE`, `OWNED_UR_ONLY`, `UR_BUDGET`, `CP_BUDGET`, inventory unknown vs zero, and explicitly supplied banlist bounds. `INDETERMINATE` never becomes `PASS` without evidence.

## Examples

Run from `master-duel/` with a private local SQLite extraction (never commit that DB):

```python
from deck_assistant import search_cards, search_effects, resolve_names, assess_deck

rows = search_cards('/private/master_duel.sqlite', name='うらら', rarity='UR')
draw = search_effects('/private/master_duel.sqlite', phrases=['ドロー'], rarity='N', limit=10)
lookup = resolve_names('/private/master_duel.sqlite', ['カオス・ソルジャー', '増殖するG'])

recipe = [{'card_id':'konami:12950','quantity':1,'section':'MAIN','core':False}, ...]
result = assess_deck('/private/master_duel.sqlite', recipe, mode='LOW_RARITY_CORE')
```

The evaluator does **not** propose recipes, attest current legality, infer card roles, or imply ability to craft: it only reports accounting and guards over supplied data. `cp_per_card` is supplied by caller and can be absent. An `UNKNOWN` owner count or unlisted/undated banlist card prevents a definite `PASS`; absence of constraints is not proof that three copies are legal. FTS/semantic facets and engine data remain later milestones.

Tests:

```bash
python -m unittest discover -s deck_assistant/tests -v
```

See [remaining milestones](../docs/INITIAL_GOAL_REMAINING_ROADMAP_20261110.md).
