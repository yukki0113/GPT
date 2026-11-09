import io, sqlite3, sys, tempfile, unittest, zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sqlite_store import Store
from zip_store.archive import NAME, pack, digest, backup
from zip_store.storage_adapter import MemoryAdapter
from zip_store.workflow import prepare, publish, inspect

def archive(entries):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in entries: z.writestr(name,data)
    return out.getvalue()

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.db=self.root/'source.sqlite'
        s=Store.create(self.db); s.add_card('fiction-1',1001,'架空竜'); s.add_card('fiction-2',1002,'架空鳥'); s.close()
        self.source,_=pack(self.db)
        self.op={'operation_id':'op-1','operation_type':'SET_INVENTORY','updates':[{'card_id':'fiction-1','owned_count':3}]}
        self.a=MemoryAdapter('parent',{'parent':self.source})
    def tearDown(self): self.tmp.cleanup()
    def prep(self): return prepare(self.source,'parent','new',self.op)
    def test_roundtrip_undo_replay(self):
        p=self.prep(); m=publish(self.a,p,'backup')
        self.assertEqual(m['verification_status'],'READBACK_VERIFIED'); self.assertEqual(self.a.read('backup'),self.source)
        self.assertEqual(digest(self.a.read('new')),m['output_zip_sha256'])
        self.assertEqual(inspect(p['zip'],'get_inventory',card_id='fiction-1')['result']['owned_count'],3)
        self.assertEqual(inspect(p['zip'],'search_cards',query='架空竜')['result'][0]['card_id'],'fiction-1')
        self.assertEqual(len(inspect(p['zip'],'history',card_id='fiction-1')['result']),1)
        self.assertEqual(prepare(p['zip'],'new','next',self.op)['diff'],p['diff'])
        undone=prepare(p['zip'],'new','undo',{'operation_id':'u','operation_type':'UNDO_INVENTORY','batch_id':'op-1'})
        self.assertEqual(inspect(undone['zip'],'get_inventory',card_id='fiction-1')['result']['known_state'],'UNKNOWN')
        with self.assertRaises(ValueError): prepare(p['zip'],'new','next',dict(self.op,updates=[{'card_id':'fiction-1','owned_count':1}]))
    def test_empty_db(self):
        path=self.root/'empty'; Store.create(path).close(); z,_=pack(path)
        self.assertEqual(inspect(z,'search_cards')['result'],[])
    def test_invalid_zip(self):
        for data in [b'broken',archive([(NAME,b'x'),('extra',b'x')]),archive([('../master_duel.sqlite',b'x')]),archive([(NAME,b'x'*1000000)])]:
            with self.subTest(size=len(data)):
                with self.assertRaises((ValueError,sqlite3.DatabaseError)): prepare(data,'parent','new',self.op)
        self.assertEqual(self.a.read('parent'),self.source)
    def test_corrupt_version_foreign_key(self):
        with self.assertRaises((ValueError,sqlite3.DatabaseError)): prepare(archive([(NAME,b'x'*200)]),'parent','new',self.op)
        s=Store(self.db); s.db.execute('INSERT INTO schema_migrations(version) VALUES (2)'); s.close()
        with self.assertRaises(ValueError): prepare(archive([(NAME,self.db.read_bytes())]),'parent','new',self.op)
        c=sqlite3.connect(self.db); c.execute('DELETE FROM schema_migrations WHERE version=2'); c.execute("INSERT INTO inventory(card_id,owned_count,known_state) VALUES ('ghost',0,'KNOWN_ZERO')"); c.commit(); c.close()
        with self.assertRaises(ValueError): prepare(archive([(NAME,self.db.read_bytes())]),'parent','new',self.op)
        self.assertEqual(self.a.read('parent'),self.source)
    def test_invalid_update_rolls_back(self):
        op=dict(self.op,updates=[{'card_id':'fiction-1','owned_count':1},{'card_id':'missing','owned_count':2}])
        with self.assertRaises(ValueError): prepare(self.source,'parent','new',op)
        self.assertEqual(inspect(self.source,'get_inventory',card_id='fiction-1')['result']['known_state'],'UNKNOWN')
    def test_stale_conflict_hash(self):
        p=self.prep(); self.a.head='other'
        with self.assertRaises(ValueError): publish(self.a,p,'backup')
        self.a.head='parent'; self.a.objects['parent']=b'changed'
        with self.assertRaises(ValueError): publish(self.a,p,'backup')
        self.a.objects['parent']=self.source; p['zip']+=b'x'
        with self.assertRaises(ValueError): publish(self.a,p,'backup')
        self.assertEqual(self.a.read('parent'),self.source)
    def test_storage_failures(self):
        class Fault(MemoryAdapter):
            def __init__(self, fail): super().__init__('parent',{'parent':source}); self.fail=fail
            def create(self,key,data):
                if self.fail=='upload' and key=='new': raise OSError('upload')
                super().create(key,data)
            def read(self,key):
                if key=='new' and self.fail=='read': raise OSError('read')
                if key=='new' and self.fail=='hash': return b'wrong'
                return super().read(key)
        source=self.source
        for fault in ('upload','read','hash'):
            adapter=Fault(fault)
            with self.subTest(fault=fault):
                with self.assertRaises((OSError,ValueError)): publish(adapter,self.prep(),'backup')
                self.assertEqual(adapter.read('parent'),self.source); self.assertEqual(adapter.read('backup'),self.source)
    def test_detect_head_change(self):
        class Changed(MemoryAdapter):
            def create(self,key,data):
                super().create(key,data)
                if key=='backup': self.head='other'
        a=Changed('parent',{'parent':self.source})
        with self.assertRaises(ValueError): publish(a,self.prep(),'backup')
        self.assertEqual(a.read('parent'),self.source); self.assertNotIn('new',a.objects)
    def test_backup_wal_and_restore(self):
        s=Store(self.db); s.db.execute('PRAGMA journal_mode=WAL'); s.add_card('fiction-3',1003,'架空花')
        target=self.root/'backup'; backup(self.db,target); s.close(); b=Store(target)
        try: self.assertIsNotNone(b.get_card('fiction-3')); self.assertTrue(b.integrity_check()['ok'])
        finally: b.close()
        p=self.prep(); publish(self.a,p,'backup')
        self.assertEqual(inspect(self.a.read('backup'),'get_inventory',card_id='fiction-1')['result']['known_state'],'UNKNOWN')

if __name__=='__main__': unittest.main()
