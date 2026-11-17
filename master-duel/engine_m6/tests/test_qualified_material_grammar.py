"""Synthetic-only coverage for conservative qualified EX source parsing."""
import unittest
from engine_m6.qualified_material_grammar import observe_qualified_header as parse


class QualifiedMaterialGrammarTests(unittest.TestCase):
    def test_xyz_attribute(self):
        r = parse("XYZ", "闇属性レベル4モンスター×2")
        self.assertEqual(r["grammar"], "QUALIFIED_XYZ_LEVEL_SOURCE_ONLY")
        self.assertEqual((r["level_required"], r["min_materials"]), (4, 2))
        self.assertEqual(r["qualifier_source"], "闇属性")
        self.assertFalse(r["qualification_verified"])

    def test_xyz_race_and_theme(self):
        for text, qualifier in (
            ("戦士族レベル4モンスター×3", "戦士族"),
            ("レベル4「仮テーマ」モンスター×2", "「仮テーマ」"),
        ):
            with self.subTest(text=text):
                self.assertEqual(parse("XYZ", text)["qualifier_source"], qualifier)

    def test_link_attribute_and_theme(self):
        r = parse("LINK", "地属性モンスター2体以上")
        self.assertEqual(r["min_materials"], 2)
        self.assertIsNone(r["max_materials"])
        self.assertEqual(r["grammar"], "QUALIFIED_LINK_COUNT_SOURCE_ONLY")
        self.assertEqual(parse("LINK", "「仮テーマ」モンスター2体")["max_materials"], 2)

    def test_link_token_exclusion_is_opaque(self):
        r = parse("LINK", "トークン以外のモンスター2体")
        self.assertEqual(r["qualifier_source"], "トークン以外の")
        self.assertFalse(r["qualification_verified"])

    def test_relational_and_alternative_are_not_simplified(self):
        for method, text in (
            ("LINK", "種族と属性が異なるモンスター2体"),
            ("LINK", "カード名が異なるモンスター2体以上"),
            ("XYZ", "レベル4モンスター×2体以上"),
            ("LINK", "チューナーを含むモンスター2体"),
            ("XYZ", "闇属性または光属性レベル4モンスター×2"),
        ):
            with self.subTest(text=text):
                self.assertEqual(parse(method, text)["grammar"], "UNPARSED")

    def test_never_authorize_summon(self):
        for method, text in (
            ("XYZ", "光属性レベル4モンスター×2"),
            ("LINK", "効果モンスター2体"),
            ("LINK", "トークン以外のモンスター2体以上"),
        ):
            r = parse(method, text)
            for k in ("qualification_verified", "summon_route_verified",
                      "simultaneous_materials_verified"):
                self.assertFalse(r[k])

    def test_wrong_method_or_missing_header(self):
        self.assertEqual(parse("FUSION", "闇属性レベル4モンスター×2")["grammar"],
                         "UNPARSED")
        self.assertEqual(parse("LINK", None)["grammar"], "UNPARSED")


if __name__ == "__main__":
    unittest.main()
