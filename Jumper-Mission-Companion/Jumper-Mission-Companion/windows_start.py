"""First-run setup and persistent diagnostics for the Windows launcher."""
from pathlib import Path
import os
import struct
import subprocess
import sys
import traceback

ROOT=Path(__file__).resolve().parent


def run_child(command,log):
    process=subprocess.Popen(command,cwd=ROOT,stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',
        env={**os.environ,'PYTHONUNBUFFERED':'1','PYTHONIOENCODING':'utf-8'})
    with process.stdout as output:
        for line in output:
            print(line,end='',flush=True);log.write(line);log.flush()
    return process.wait()


def main():
    os.chdir(ROOT)
    if sys.version_info[:2] not in [(3,12),(3,13)] or struct.calcsize('P')!=8:
        print('Use 64-bit Python 3.12 or 3.13: https://www.python.org/downloads/windows/')
        return 1
    log_path=ROOT/'windows-startup.log'
    with log_path.open('w',encoding='utf-8') as log:
        log.write(f'Python: {sys.version}\nExecutable: {sys.executable}\nFolder: {ROOT}\n')
        print('Jumper Mission Companion\n')
        print('First launch installs dependencies and downloads the official robot project.')
        print('Keep this window open. Internet is needed for setup.\n')
        python=ROOT/'.venv'/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
        if not python.exists() or not (ROOT/'.setup-complete').exists():
            code=run_child([sys.executable,'-u','setup.py'],log)
            if code:
                print(f'\nSetup failed. Details are in {log_path.name}.')
                return code
        print('\nStarting the local application...')
        code=run_child([str(python),'-u','launch.py','--open-browser'],log)
        if code:print(f'\nApplication failed. Details are in {log_path.name}.')
        return code


if __name__=='__main__':
    try:raise SystemExit(main())
    except KeyboardInterrupt:print('\nApplication stopped.');raise SystemExit(0)
    except Exception:
        message=traceback.format_exc();print(message)
        try:
            with (ROOT/'windows-startup.log').open('a',encoding='utf-8') as f:f.write(message)
        except OSError:pass
        raise SystemExit(1)
