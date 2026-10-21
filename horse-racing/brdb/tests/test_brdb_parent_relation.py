from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import brdb_parent_relation as relation  # noqa: E402


class ParentRelationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sire = {
            "horse_id": "S1",
            "horse_name": "父A",
            "sex_code": "1",
            "birth_date": "20100101",
            "sire_line_code": "1206",
        }
        self.dam = {
            "horse_id": "D1",
            "horse_name": "母A",
            "sex_code": "2",
            "birth_date": "20150101",
            "sire_name": "母父A",
            "sire_birth_year": 2006,
            "sire_line_code": "1503",
        }
        self.bms = {
            "horse_id": "B1",
            "horse_name": "母父A",
            "sex_code": "1",
            "birth_date": "20060101",
            "sire_line_code": "1503",
        }
        self.master = relation.HorseMasterIndex([self.sire, self.dam, self.bms])

    def child(self) -> dict:
        return {
            "horse_id": "C1",
            "horse_name": "仔",
            "sire_name": "父A",
            "sire_birth_year": 2010,
            "sire_line_code": "1206",
            "dam_name": "母A",
            "dam_birth_year": 2015,
            "broodmare_sire_name": "母父A",
            "broodmare_sire_birth_year": 2006,
            "broodmare_sire_line_code": "1503",
        }

    def test_resolves_all_first_generation_with_independent_guards(self) -> None:
        got = relation.resolve_first_generation(self.child(), master=self.master)
        self.assertEqual(got["sire"].status, relation.STATUS_RESOLVED_EXACT)
        self.assertEqual(got["dam"].status, relation.STATUS_RESOLVED_EXACT)
        self.assertEqual(
            got["broodmare_sire"].status,
            relation.STATUS_RESOLVED_EXACT,
        )
        self.assertEqual(got["dam"].resolved_horse_id, "D1")

    def test_dam_false_collision_fails_closed(self) -> None:
        false_dam = {
            "horse_id": "15101582",
            "horse_name": "ヴィヴァルダ",
            "sex_code": "2",
            "birth_date": "20150429",
            "sire_name": "アンテロ",
            "sire_birth_year": 2010,
            "sire_line_code": "1109",
        }
        child = {
            "horse_id": "22110095",
            "horse_name": "トーセンビギン",
            "dam_name": "ヴィヴァルダ",
            "dam_birth_year": 2015,
            "broodmare_sire_name": "サウスデール",
            "broodmare_sire_birth_year": 2006,
            "broodmare_sire_line_code": "1503",
        }
        got = relation.resolve_parent(
            child,
            relation.ROLE_DAM,
            master=relation.HorseMasterIndex([false_dam]),
        )
        self.assertEqual(got.status, relation.STATUS_CONFLICT)
        self.assertIsNone(got.resolved_horse_id)

    def test_explicit_alias_allows_dam_guard(self) -> None:
        dam = dict(self.dam)
        dam["sire_name"] = "ロックオヴジブラルタル"
        dam["sire_birth_year"] = 1999
        dam["sire_line_code"] = "1106"
        child = self.child()
        child["broodmare_sire_name"] = "ロックオブジブラルタル"
        child["broodmare_sire_birth_year"] = 1999
        child["broodmare_sire_line_code"] = "1106"
        aliases = relation.AliasIndex([
            relation.NameAlias(
                observed_name="ロックオブジブラルタル",
                canonical_name="ロックオヴジブラルタル",
                birth_year=1999,
                lineage_code="1106",
                alias_version="test-v1",
                evidence_type="UKC_AUDIT",
            )
        ])
        got = relation.resolve_parent(
            child,
            relation.ROLE_DAM,
            master=relation.HorseMasterIndex([dam]),
            aliases=aliases,
        )
        self.assertEqual(got.status, relation.STATUS_RESOLVED_ALIAS)
        self.assertEqual(got.resolved_horse_id, "D1")

    def test_same_name_birth_year_multiple_candidates_is_not_resolved(self) -> None:
        duplicate = dict(self.sire)
        duplicate["horse_id"] = "S2"
        got = relation.resolve_parent(
            self.child(),
            relation.ROLE_SIRE,
            master=relation.HorseMasterIndex([self.sire, duplicate]),
        )
        self.assertEqual(got.status, relation.STATUS_MULTIPLE_CANDIDATES)
        self.assertIsNone(got.resolved_horse_id)

    def test_sire_lineage_conflict_is_not_resolved(self) -> None:
        child = self.child()
        child["sire_line_code"] = "1109"
        got = relation.resolve_parent(
            child,
            relation.ROLE_SIRE,
            master=self.master,
        )
        self.assertEqual(got.status, relation.STATUS_CONFLICT)
        self.assertIsNone(got.resolved_horse_id)

    def test_missing_guard_is_not_silently_accepted(self) -> None:
        child = self.child()
        child["sire_line_code"] = ""
        got = relation.resolve_parent(
            child,
            relation.ROLE_SIRE,
            master=self.master,
        )
        self.assertEqual(got.status, relation.STATUS_INSUFFICIENT_GUARD)

    def test_no_candidate_remains_unresolved(self) -> None:
        child = self.child()
        child["sire_name"] = "存在しない父"
        got = relation.resolve_parent(
            child,
            relation.ROLE_SIRE,
            master=self.master,
        )
        self.assertEqual(got.status, relation.STATUS_NO_CANDIDATE)
        self.assertIsNone(got.resolved_horse_id)


if __name__ == "__main__":
    unittest.main()
