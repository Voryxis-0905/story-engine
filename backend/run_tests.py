"""Run tests with temporary storage and outgoing provider HTTP disabled."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--legacy', action='store_true', help='Run the old sequential regression script')
args = parser.parse_args()
backend = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='story-engine-tests-') as temporary:
    env = dict(os.environ, STORY_ENGINE_DATA_DIR=temporary, OPENROUTER_API_KEY='', PYTHONIOENCODING='utf-8')
    if args.legacy:
        program = (
            "import runpy, requests; "
            "requests.sessions.Session.send=lambda *a,**k: (_ for _ in ()).throw(AssertionError('Real HTTP forbidden in tests')); "
            "runpy.run_path('test_engine.py',run_name='__main__')"
        )
        command = [sys.executable, '-c', program]
    else:
        command = [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v']
    result = subprocess.run(command, cwd=backend, env=env)
sys.exit(result.returncode)
