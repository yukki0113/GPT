"""Synthetic-only official page byte/cid anchor tests."""
import unittest
from engine_m6.official_identity_candidates import (
    stage_official_card_identity,OfficialIdentityInputError,
)

class OfficialIdentityCandidateTests(unittest.TestCase):
    def setUp(self):
        self.data=dict(
            card_id='konami:13543',expected_name='Ｘ・ＨＥＲＯ ワンダー・ドライバー',
            source_url=('https://www.db.yugioh-card.com/yugiohdb/card_search.action'
                        '?cid=13543&ope=2&request_locale=ja'),
            source_bytes=('<html><h1>エクストラヒーロー X・HERO ワンダー・ドライバー '
                          'Xtra HERO Wonder Driver</h1><p>カードテキスト</p></html>').encode(),
            fetched_at_utc='2026-11-18T00:00:00Z')

    def call(self,**changes):
        return stage_official_card_identity(**(self.data|changes))

    def test_exact_source_bytes_and_id_but_no_membership_promotion(self):
        r=self.call()
        self.assertEqual(r['card_id'],'konami:13543')
        self.assertEqual(r['official_card_identity'],'SOURCE_HEADER_ALIGNED_CANDIDATE')
        for name in ('archetype_membership','master_duel_coverage','material_eligibility'):
            self.assertEqual(r[name],'UNVERIFIED')
        self.assertEqual(r['review_status'],'NOT_REVIEWED')
        import hashlib
        self.assertEqual(r['source_document_sha256'],
                         hashlib.sha256(self.data['source_bytes']).hexdigest())

    def test_wrong_cid_and_url_lookalikes(self):
        for url in (
            'https://www.db.yugioh-card.com.evil.test/yugiohdb/card_search.action?cid=13543&ope=2&request_locale=ja',
            'https://evil.test/yugiohdb/card_search.action?cid=13543&ope=2&request_locale=ja',
            'http://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=13543&ope=2&request_locale=ja',
            'https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=13542&ope=2&request_locale=ja',
            'https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=13543&ope=2&request_locale=ja&cid=13543',
        ):
            with self.subTest(url=url),self.assertRaises(OfficialIdentityInputError):
                self.call(source_url=url)

    def test_related_card_name_in_body_is_not_main_identity(self):
        raw=('<html><h1>架空の別カード</h1><p>カードテキスト：'
             'X・HERO ワンダー・ドライバー</p></html>').encode()
        with self.assertRaisesRegex(OfficialIdentityInputError,'HEADER'):
            self.call(source_bytes=raw)

    def test_invalid_encoding_and_no_timezone(self):
        for update in ({'source_bytes':b'\xff\xfe'},
                       {'fetched_at_utc':'2026-11-18T00:00:00'}):
            with self.assertRaises(OfficialIdentityInputError):
                self.call(**update)

    def test_changed_name_rejected_even_with_matching_cid(self):
        with self.assertRaises(OfficialIdentityInputError):
            self.call(expected_name='Ｘ・ＨＥＲＯ ドレッドバスター')

if __name__=='__main__':
    unittest.main()
