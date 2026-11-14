"""Exercise the installed package outside its source directory."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary)
    def call(*args):
        process=subprocess.run([sys.executable,'-I','-m','cloud_edge',*args],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if process.returncode:
            raise RuntimeError(process.stderr.decode('utf8',errors='replace'))
        return process.stdout.decode('utf8')
    call('scenario','--output','scenario.json')
    call('run','--input','scenario.json','--output','run')
    report=json.loads((root/'run/report.json').read_text(encoding='utf8'))
    assert len(report['results'])==4 and (root/'run/summary.csv').is_file()
print('PASS: installed CLI runs outside the source tree')
