"""Run the existing offline pilot in P01's new workspace, without local settings.

This is an automated technical check. P01 is a fictional persona, not a person
using the browser. The stock demo identity remains Community offline demo.
"""
from pathlib import Path
import os
import runpy
import sys
import types


ROOT = Path(__file__).resolve().parents[3]
OWNED = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["OPENAI_API_KEY"] = ""
# The test settings import defaults from settings.py. Do not load the user's
# local_settings module even though test_settings replaces database and keys.
sys.modules["regulai.local_settings"] = types.ModuleType("regulai.local_settings")
sys.argv = [str(ROOT / "scripts/pilot_document_demo.py"),
            "--workspace", str(OWNED / "browser01"), "--port", "8781"]
runpy.run_path(sys.argv[0], run_name="__main__")
