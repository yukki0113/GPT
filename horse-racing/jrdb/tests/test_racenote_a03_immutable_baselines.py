"""A03: immutable external baseline contract, without network access."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "horse-racing/jrdb/config/public_drive/racenote_a03_accepted_baselines_v1.json"

def test_manifest_identity_and_hashes():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1 and data["transport"] == "public_google_drive"
    rows = {x["artifact_id"]: x for x in data["artifacts"]}
    assert len(rows) == len(data["artifacts"]) == 4
    assert {key: (v["file_id"],v["expected_size"],v["sha256"]) for key,v in rows.items()} == {
      "rrdb_validation_g38327108923": ("1xbOGJzGIQsXaHUYhKMuRfy1UfmgHEhYY",47451277,"ea1d4e1f3f0efdebee512a3ba09f7f9fd253a3851b42c562698bc11102fb011a"),
      "course_fit_v01_part1": ("1ljLg_jxVdZtpJ_Aqku0L93y8nwnfXUTQ",79086971,"b27f2293a100755aa1ac0c902c2e6338a8393cd208c5de0912ff7a81f89783ba"),
      "course_fit_v01_part2": ("1yxP0EtPRmcTnrAgmgBMlAAj257r3pgYE",91263391,"ddc07eca88fe1b56391efcaa3b84ff4cf34121f69c7262a024177b82702dea72"),
      "racelap_canonical_20261017": ("1q7pmoTRsg27d--xi5HhtTaJXAI_TdzUi",1663722,"a4b076e69e9d26c464b49fd8301640b07e89fbd28925a88229869a465a51ae96"),
    }
    for row in rows.values():
        assert row["destination"].split("/")[-1] == row["expected_name"]
        assert len(row["sha256"]) == 64 and row["expected_size"] > 0

def test_consumers_no_longer_reference_expiring_actions_artifacts():
    expected = {
      ".github/workflows/rrdb_horse_course_fit_validation.yml": ("rrdb_validation_g38327108923",),
      ".github/workflows/racenote_v056_btday_turn1_shared.yml": ("course_fit_v01_part1","course_fit_v01_part2","racelap_canonical_20261017"),
      ".github/workflows/racenote_v055_r6_btday_turn1_shared.yml": ("course_fit_v01_part1","course_fit_v01_part2","racelap_canonical_20261017"),
      ".github/workflows/racenote_historical_v052_equivalence.yml": ("course_fit_v01_part1","course_fit_v01_part2"),
    }
    for path,artifacts in expected.items():
        body=(ROOT/path).read_text(encoding="utf-8")
        assert MANIFEST.relative_to(ROOT).as_posix() in body
        assert "actions/artifacts/11780924435" not in body
        assert "actions/artifacts/11799761734" not in body
        assert "actions/artifacts/12101869150" not in body
        for artifact in artifacts:
            assert f"--artifact {artifact}" in body
    for path in (".github/workflows/racenote_v056_btday_turn1_shared.yml",".github/workflows/racenote_v055_r6_btday_turn1_shared.yml"):
        body=(ROOT/path).read_text(encoding="utf-8")
        assert "unzip -qn " in body
        assert "assert manifest['generation_id']=='racelap-forward-canonical-20261017-01'" in body
