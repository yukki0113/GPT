"""Byte-pinned, reviewer-declared identity ledger; NEVER summon authorization.

Document SHA proves byte identity, not official authority. Token state belongs
to a unique board instance and snapshot, never a card ID. Output matches the
optional M6-5B identity_evidence contract and remains REQUIRES_REVIEW.
"""
from __future__ import annotations
from hashlib import sha256
import re
from .identity_material_evidence import observe_identity_header

CID=re.compile(r'konami:[0-9]+\Z')
SHA=re.compile(r'[0-9a-f]{64}\Z')
KEY=re.compile(r'[A-Za-z0-9][A-Za-z0-9:._/-]{0,199}\Z')
DOC={'document_id','sha256','media_type','source_locator','review_status'}
MEMBER={'card_id','archetype_label','is_member','document_id','review_status'}
BOARD={'instance_id','card_id','board_snapshot_id','is_token','document_id','review_status'}

class LedgerContractError(ValueError):
    """Invalid/private evidence; error string contains no source values."""


def compile_identity_evidence(*, method, material_header, extra_card_id,
                              material_card_ids, occurrence_instance_ids,
                              master_sqlite_sha256, documents, document_bytes,
                              membership_rows, board_rows, board_snapshot_id=None):
    spec=observe_identity_header(method,material_header)
    if spec is None: raise LedgerContractError('LEDGER_SOURCE_GRAMMAR_UNSUPPORTED')
    ids=material_card_ids
    if (not isinstance(master_sqlite_sha256,str) or not SHA.fullmatch(master_sqlite_sha256)
        or not isinstance(extra_card_id,str) or not CID.fullmatch(extra_card_id)
        or not isinstance(ids,(list,tuple)) or not 1<=len(ids)<=8
        or any(not isinstance(cid,str) or not CID.fullmatch(cid) for cid in ids)):
        raise LedgerContractError('LEDGER_MASTER_OR_MATERIAL_PIN_INVALID')
    if (not isinstance(documents,list) or not isinstance(document_bytes,dict)
        or not isinstance(membership_rows,list) or not isinstance(board_rows,list)):
        raise LedgerContractError('LEDGER_CONTAINER_CONTRACT')
    docs={}
    for d in documents:
        if not isinstance(d,dict) or set(d)!=DOC:
            raise LedgerContractError('LEDGER_DOCUMENT_SCHEMA')
        key=d['document_id']
        if not isinstance(key,str) or not KEY.fullmatch(key) or key in docs:
            raise LedgerContractError('LEDGER_DOCUMENT_ID')
        if (not isinstance(d['sha256'],str) or not SHA.fullmatch(d['sha256'])
            or d['review_status'] not in ('REVIEWED','NOT_REVIEWED')
            or d['media_type'] not in ('text/plain','text/html','application/pdf','application/json')
            or not isinstance(d['source_locator'],str) or not d['source_locator'].strip()):
            raise LedgerContractError('LEDGER_DOCUMENT_FIELDS')
        raw=document_bytes.get(key)
        if not isinstance(raw,bytes) or sha256(raw).hexdigest()!=d['sha256']:
            raise LedgerContractError('LEDGER_DOCUMENT_BYTES_SHA_MISMATCH')
        docs[key]=d
    if set(docs)!=set(document_bytes):
        raise LedgerContractError('LEDGER_DOCUMENT_BLOB_SET_MISMATCH')
    def rows(source, keys, label):
        seen={}
        for r in source:
            if not isinstance(r,dict) or set(r)!=keys:
                raise LedgerContractError('LEDGER_'+label+'_SCHEMA')
            if (not isinstance(r['card_id'],str) or not CID.fullmatch(r['card_id'])
                or not isinstance(r['document_id'],str) or r['document_id'] not in docs
                or r['review_status'] not in ('REVIEWED','NOT_REVIEWED')):
                raise LedgerContractError('LEDGER_'+label+'_FIELDS')
            if label=='MEMBERSHIP':
                if (not isinstance(r['archetype_label'],str)
                    or not r['archetype_label'].strip() or type(r['is_member']) is not bool):
                    raise LedgerContractError('LEDGER_MEMBERSHIP_VALUE')
                k=(r['card_id'],r['archetype_label'])
            else:
                if (not isinstance(r['instance_id'],str) or not KEY.fullmatch(r['instance_id'])
                    or not isinstance(r['board_snapshot_id'],str)
                    or not KEY.fullmatch(r['board_snapshot_id'])
                    or type(r['is_token']) is not bool):
                    raise LedgerContractError('LEDGER_BOARD_VALUE')
                k=(r['board_snapshot_id'],r['instance_id'])
            if k in seen:
                raise LedgerContractError('LEDGER_'+label+'_DUPLICATE_OR_CONFLICT')
            seen[k]=r
        return seen
    membership=rows(membership_rows,MEMBER,'MEMBERSHIP')
    board=rows(board_rows,BOARD,'BOARD')
    if spec['predicate']=='NOT_TOKEN':
        v=occurrence_instance_ids
        if (not isinstance(board_snapshot_id,str) or not KEY.fullmatch(board_snapshot_id)
            or not isinstance(v,(list,tuple)) or len(v)!=len(ids)
            or any(not isinstance(x,str) or not KEY.fullmatch(x) for x in v)
            or len(set(v))!=len(v)):
            raise LedgerContractError('LEDGER_BOARD_OCCURRENCE_INVALID')
    elif occurrence_instance_ids not in (None,(),[]):
        raise LedgerContractError('LEDGER_MEMBERSHIP_INSTANCES_NOT_REQUIRED')
    claims=[]
    for index,cid in enumerate(ids):
        if spec['predicate']=='ARCHETYPE_MEMBERSHIP':
            row=membership.get((cid,spec['label']))
        else:
            row=board.get((board_snapshot_id,occurrence_instance_ids[index]))
            if row and row['card_id']!=cid:
                raise LedgerContractError('LEDGER_BOARD_INSTANCE_CARD_MISMATCH')
        if row is None: raise LedgerContractError('LEDGER_REQUIRED_CLAIM_MISSING')
        doc=docs[row['document_id']]
        if doc['review_status']!='REVIEWED' or row['review_status']!='REVIEWED':
            raise LedgerContractError('LEDGER_SOURCE_OR_CLAIM_NOT_REVIEWED')
        claims.append(dict(
            card_id=cid,predicate=spec['predicate'],label=spec['label'],
            # Existing M6 contract: NOT_TOKEN claim=False means non-token.
            claim=(row['is_member'] if spec['predicate']=='ARCHETYPE_MEMBERSHIP'
                   else row['is_token']),
            source_ref=row['document_id'],source_document_sha256=doc['sha256'],
            review_status='REVIEWED'))
    return dict(master_sqlite_sha256=master_sqlite_sha256,
                extra_card_id=extra_card_id,
                material_header_sha256=sha256(material_header.encode()).hexdigest(),
                occurrences=claims)
