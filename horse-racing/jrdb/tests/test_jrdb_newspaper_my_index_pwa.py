"""Retired UI regression entrypoint retained for the Pages gate."""
import subprocess
import unittest
from pathlib import Path
class RetiredUiTest(unittest.TestCase):
    def test_legacy_addons_cannot_restore_ui(self):
        subprocess.run(["node", str(Path(__file__).with_name("test_newspaper_edge_v05_production.cjs"))], check=True)
