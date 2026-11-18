"""Strict source-byte staging for KONAMI OCG card identity.

This creates candidate observations only. Official card identity is not proof
of archetype membership, Master Duel availability, or material eligibility.
No network client: callers supply the original downloaded response bytes.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from html.parser import HTMLParser
import re
import unicodedata
from urllib.parse import parse_qs, urlsplit

CID=re.compile(r'konami:[1-9][0-9]*\Z')

class OfficialIdentityInputError(ValueError):
    """Reject a compromised, ambiguous, or insufficient source snapshot."""

class _HeaderParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_h1=False
        self.h1=[]
        self.text=[]
    def handle_starttag(self,tag,attrs):
        if tag=='h1':
            self.in_h1=True
            self.text=[]
    def handle_data(self,data):
        if self.in_h1:self.text.append(data)
    def handle_endtag(self,tag):
        if tag=='h1' and self.in_h1:
            self.h1.append(''.join(self.text).strip())
            self.in_h1=False
            self.text=[]

def _norm(value):
    return unicodedata.normalize('NFKC',value)

def stage_official_card_identity(*, card_id, expected_name,
                                 source_url, source_bytes, fetched_at_utc):
    """Require official URL CID + one unambiguous name in card-detail h1.

    This is a provenance-locked candidate; REVIEWED evidence rows are NOT
    generated. A URL and source SHA alone cannot prove authenticity.
    """
    if (not isinstance(card_id,str) or not CID.fullmatch(card_id)
        or not isinstance(expected_name,str) or not expected_name.strip()
        or not isinstance(source_bytes,bytes) or not source_bytes
        or len(source_bytes)>3_000_000):
        raise OfficialIdentityInputError('OFFICIAL_IDENTITY_INPUT_INVALID')
    parsed=urlsplit(source_url) if isinstance(source_url,str) else None
    if (not parsed or parsed.scheme!='https'
        or parsed.hostname!='www.db.yugioh-card.com'
        or parsed.username or parsed.password or parsed.port is not None
        or parsed.path!='/yugiohdb/card_search.action'):
        raise OfficialIdentityInputError('OFFICIAL_IDENTITY_URL_NOT_TRUSTED')
    query=parse_qs(parsed.query,keep_blank_values=True)
    if (set(query) != {'cid','ope','request_locale'}
        or any(len(v)!=1 for v in query.values())
        or query['cid'][0]!=card_id.removeprefix('konami:')
        or query['ope']!=['2'] or query['request_locale']!=['ja']):
        raise OfficialIdentityInputError('OFFICIAL_IDENTITY_CID_QUERY_MISMATCH')
    try:
        when=datetime.fromisoformat(fetched_at_utc.replace('Z','+00:00'))
        if when.tzinfo is None or when.utcoffset().total_seconds()!=0:
            raise ValueError('not UTC')
        html=source_bytes.decode('utf-8',errors='strict')
    except (ValueError,UnicodeError,AttributeError,TypeError):
        raise OfficialIdentityInputError('OFFICIAL_IDENTITY_BYTES_OR_TIME_INVALID')
    parser=_HeaderParser()
    parser.feed(html)
    # Site headings may include readings/translations; require the exact
    # canonical name as an uninterrupted substring of the header only.
    canonical=_norm(expected_name.strip())
    matches=[h for h in parser.h1 if canonical in _norm(h)]
    if len(matches) not in (1,2) or not any('カード' in _norm(html) for _ in (0,)):
        raise OfficialIdentityInputError('OFFICIAL_IDENTITY_HEADER_AMBIGUOUS')
    return {
        'schema':'md-official-card-identity-candidate-v1',
        'card_id':card_id,
        'expected_name':expected_name,
        'source_url':source_url,
        'source_document_sha256':sha256(source_bytes).hexdigest(),
        'fetched_at_utc':fetched_at_utc,
        'official_card_identity':'SOURCE_HEADER_ALIGNED_CANDIDATE',
        'archetype_membership':'UNVERIFIED',
        'master_duel_coverage':'UNVERIFIED',
        'material_eligibility':'UNVERIFIED',
        'review_status':'NOT_REVIEWED',
    }
