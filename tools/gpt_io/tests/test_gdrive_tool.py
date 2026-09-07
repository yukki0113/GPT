import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.gpt_io.common.result import build_result
from tools.gpt_io.gdrive import gdrive_api as api
from tools.gpt_io.gdrive.gdrive_tool import execute, validate_request

class RequestTests(unittest.TestCase):
    def test_unsupported(self):
        with self.assertRaises(ValueError): validate_request({"operation":"delete"})
    def test_no_overwrite(self):
        with self.assertRaises(ValueError): validate_request({"operation":"upload","parent_folder_id":"x","local_path":"x","overwrite":True})
    def test_destructive_requires_id(self):
        with self.assertRaises(ValueError): validate_request({"operation":"trash"})
    def test_replace_cas(self):
        with self.assertRaises(ValueError): validate_request({"operation":"replace","file_id":"x","expected":{"file_id":"y"},"local_path":"x"})
    def test_result_schema(self):
        r=build_result(status="success",backend="gdrive",operation="x",request_id="r",source={},destination={},size_bytes=0,sha256="",provenance={})
        self.assertEqual(set(r), {"status","backend","operation","request_id","source","destination","size_bytes","sha256","provenance"})

class FakeRequest:
    def __init__(self,value): self.value=value
    def execute(self): return self.value
class FakeFiles:
    def __init__(self,metas): self.metas=metas
    def get(self, fileId, **kwargs): return FakeRequest(self.metas[fileId])
class FakeService:
    def __init__(self,metas): self._files=FakeFiles(metas)
    def files(self): return self._files

class BoundaryTests(unittest.TestCase):
    def test_parent_chain(self):
        s=FakeService({"child":{"parents":["parent"]},"parent":{"parents":["root"]}})
        self.assertTrue(api.is_under_root(s,"child","root"))
    def test_outside_root(self):
        s=FakeService({"child":{"parents":["elsewhere"]},"elsewhere":{"parents":[]}})
        with self.assertRaises(api.DriveError): api.assert_under_root(s,"child","root")
    def test_move_outside_root(self):
        s=FakeService({"file":{"parents":["root"]},"outside":{"parents":[]}})
        with self.assertRaises(api.DriveError): api.move(s,"file","outside","root")
    def test_trash_outside_root(self):
        s=FakeService({"file":{"parents":[]}})
        with self.assertRaises(api.DriveError): api.trash(s,"file","root")
    def test_download_sha_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(api,"download",return_value={"size_bytes":1,"sha256":"bad"}), patch.object(api,"assert_under_root"):
                with self.assertRaises(api.DriveError): execute({"operation":"verify","file_id":"f","output":str(Path(d)/"x"),"expected":{"sha256":"good"}},object(),"root")
    def test_auth_error_redacts_secret(self):
        with patch.dict("os.environ",{api.SERVICE_ACCOUNT_ENV:"top-secret",api.ROOT_ENV:"r"},clear=True):
            with self.assertRaisesRegex(api.DriveError,"authentication failed") as caught: api.load_service()
            self.assertNotIn("top-secret",str(caught.exception))

if __name__ == "__main__": unittest.main()
