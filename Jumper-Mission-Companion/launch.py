"""Launch the local dashboard and open the browser after startup."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from server import VERSION

ROOT=Path(__file__).resolve().parent


def wait_and_open(process,url,timeout=90):
    until=time.monotonic()+timeout
    while time.monotonic()<until and process.poll() is None:
        try:
            with urllib.request.urlopen(url+'/api/state',timeout=2) as response:state=json.load(response)
            if state.get('fault'):
                print('Startup fault:',state['fault'],flush=True);return
            webbrowser.open(url);print('Dashboard ready:',url,flush=True);return
        except (OSError,ValueError):time.sleep(.4)
    if process.poll() is None:print('Open the dashboard manually:',url,flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--open-browser',action='store_true');p.add_argument('--view',choices=['browser','map','image'],default='browser');args=p.parse_args()
    config=json.loads((ROOT/'local-config.json').read_text()) if (ROOT/'local-config.json').exists() else {}
    upstream=config.get('upstream',str(ROOT.parent/'jumper-upstream'))
    try:
        with urllib.request.urlopen('http://127.0.0.1:8765/api/config',timeout=2) as response:existing=json.load(response)
    except (OSError,ValueError):existing=None
    if existing:
        if existing.get('version')==VERSION and existing.get('backend')=='native':
            print('Jumper is already running. Reusing the dashboard.',flush=True)
            if args.open_browser:webbrowser.open('http://127.0.0.1:8765')
            return 0
        print('An older or different server is using port 8765. Close its terminal, then start Jumper again.',flush=True)
        return 1
    process=subprocess.Popen([sys.executable,'-u',str(ROOT/'server.py'),'--upstream',upstream,'--view',args.view],cwd=ROOT)
    if args.open_browser:
        threading.Thread(target=wait_and_open,args=(process,'http://127.0.0.1:8765'),daemon=True).start()
    try:return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill()
        return 0


if __name__=='__main__':raise SystemExit(main())
