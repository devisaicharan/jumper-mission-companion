"""Run the production WSGI entrypoint and isolated browser visitor checks."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

root=Path(__file__).resolve().parents[1]
env=os.environ.copy();env.update(PORT='8773',PUBLIC_ORIGIN='http://127.0.0.1:8773',HOSTED_LOCAL_TEST='1',MAX_SESSIONS='2',MISSION_BACKEND=env.get('MISSION_BACKEND','native'),UPSTREAM_DIR=str(root.parent/'jumper-upstream'))
log=(root/'docs/hosted-test.log').open('w')
server=subprocess.Popen([sys.executable,'cloud_start.py'],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
try:
    for _ in range(150):
        if server.poll() is not None:raise RuntimeError('Hosted server exited; read docs/hosted-test.log')
        try:urllib.request.urlopen('http://127.0.0.1:8773/healthz',timeout=1).close();break
        except OSError:time.sleep(.1)
    else:raise RuntimeError('Hosted server did not start')
    subprocess.run(['node','tests/hosted_ui_check.cjs'],cwd=root,env=env,check=True)
finally:
    server.terminate()
    try:server.wait(timeout=10)
    except subprocess.TimeoutExpired:server.kill();server.wait()
    log.close()
