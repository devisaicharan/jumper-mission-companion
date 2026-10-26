import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

root=Path(__file__).resolve().parents[1]
server=subprocess.Popen([sys.executable,'server.py','--backend','native','--port','8767'],cwd=root)
try:
    for _ in range(200):
        try:
            urllib.request.urlopen('http://127.0.0.1:8767/api/state',timeout=1).close();break
        except OSError:time.sleep(.1)
    else:raise RuntimeError('Native server did not start')
    subprocess.run(['node','tests/native_ui_check.cjs'],cwd=root,env=os.environ,check=True)
finally:
    server.terminate()
    try:server.wait(timeout=5)
    except subprocess.TimeoutExpired:server.kill()
