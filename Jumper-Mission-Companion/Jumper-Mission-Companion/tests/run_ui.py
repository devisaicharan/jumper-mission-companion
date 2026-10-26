"""Start an isolated test server and run the browser check in one process tree."""
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

root=Path(__file__).resolve().parents[1]
server=subprocess.Popen([sys.executable,'server.py','--backend','preview','--port','8766'],cwd=root)
try:
    for _ in range(80):
        try:
            urllib.request.urlopen('http://127.0.0.1:8766/api/state',timeout=1).close()
            break
        except OSError:time.sleep(.1)
    else:raise RuntimeError('Test server did not start')
    subprocess.run(['node','tests/ui_check.cjs'],cwd=root,env=os.environ,check=True)
finally:
    server.terminate()
    try:server.wait(timeout=5)
    except subprocess.TimeoutExpired:server.kill()
