import unittest
from tools.gpt_io.gdrive.gdrive_tool import validate_request
class DriveSafetyTests(unittest.TestCase):
 def test_no_overwrite(self):
  with self.assertRaises(ValueError): validate_request({"operation":"upload","parent_folder_id":"x","overwrite":True})
 def test_cas(self):
  with self.assertRaises(ValueError): validate_request({"operation":"replace","file_id":"x"})
