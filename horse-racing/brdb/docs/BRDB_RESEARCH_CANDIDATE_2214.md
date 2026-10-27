# BRDB research candidate from daily PACI UKC

This command builds an immutable research generation separate from BRDB CURRENT.
It requires a validated 27-archive annual UKC generation and the fixed #2212
108-row audit, denominator, and PACI inventory. It independently rescans the
original UKC members in each SHA-pinned PACI ZIP and adds the 104 exact IDs
found in those sources. Four unmatched IDs remain unknown.

Run `src/build_brdb_research_candidate.py` with `--base-generation`,
`--annual-dir`, `--paci-dir`, `--inventory`, `--audit`, `--denominator`, and
`--output-root`. The annual and PACI directories must contain files named in
the supplied manifests. The command verifies their sizes and SHA-256 values.
To add later PACI files, extend the audited inventory with their exact ZIP
name, size, SHA-256, UKC member list, and UKC record count; then rebuild into
a new output root. An existing generation directory is never overwritten.

The candidate generation ID hashes the builder code, base manifest, audit,
denominator, inventory, all source ZIP hashes, and the selection rule. The
chosen daily profile is the latest valid profile data date, then archive date,
then source location. `99999999` dates are quarantined. Conflicting semantic
profiles on the chosen date fail the build. Annual facts win for existing IDs;
additional daily IDs are never allowed to overwrite annual IDs.

The four standard Parquet tables and `manifest.json` retain the v0.1 schema.
`added_104.json`, `observation_history.json`, `relation_diff.json`, and
`audit.json` give row-level source, selection, parent resolution, and conflict
evidence. The observation history records both the PACI archive date and UKC
profile data date. The builder uses the existing guarded parent resolver and
records unresolved candidate IDs as unknown.

Use `src/brdb_research_reader.py` with an explicit generation path and an
`as_of=YYYYMMDD` for each individual or batch query. A newly observed daily
horse is unavailable before its first source archive date. This research reader
does not change CURRENT or any production consumer.
