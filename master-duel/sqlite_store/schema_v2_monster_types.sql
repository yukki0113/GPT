-- Additive v2 migration for existing v1 private MD SQLite snapshots.
-- Keep v1 cards, inventory, banlist, effects and indexes byte-for-byte.
-- Required source backfill: card_master_import/monster_types_migration.py
-- Never apply DDL alone and promote an empty classification table.
CREATE TABLE card_monster_types (
    card_id TEXT NOT NULL REFERENCES cards(card_id),
    monster_type TEXT NOT NULL CHECK(monster_type IN
      ('NORMAL','EFFECT','FUSION','SYNCHRO','XYZ','LINK','RITUAL',
       'PENDULUM','TUNER','FLIP','GEMINI','SPIRIT','UNION','TOON')),
    source TEXT NOT NULL, verification TEXT NOT NULL DEFAULT 'UNVERIFIED_SOURCE',
    PRIMARY KEY(card_id,monster_type)
);
CREATE INDEX idx_card_monster_types_type ON card_monster_types(monster_type,card_id);
-- INSERT INTO schema_migrations(version) VALUES(2) only after full source-matched backfill.
