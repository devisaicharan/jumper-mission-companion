"""Set up an isolated local environment and the pinned official Jumper assets."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import venv
import zipfile

ROOT=Path(__file__).resolve().parent
COMMIT='b2e58669848a3ba4f209597cd6bebdfe9d0533a4'
URL='https://github.com/KingKongRobotics/jumper.git'


def check_source(upstream):
    if (upstream/'.git').is_dir():
        if not shutil.which('git'):raise RuntimeError('This existing source is a Git checkout. Install Git or choose a new --upstream folder.')
        actual=subprocess.check_output(['git','-C',str(upstream),'rev-parse','HEAD'],text=True).strip()
    else:
        marker=upstream/'.mission-source.json'
        actual=json.loads(marker.read_text()).get('commit') if marker.is_file() else None
    if actual!=COMMIT:
        raise RuntimeError(f'Existing source folder is not the pinned Jumper revision. Nothing overwritten: {upstream}')
    for path in ['assets/jumper/jumper.xml','out/bundle_example/jumper/bundle.json']:
        if not (upstream/path).is_file():raise RuntimeError(f'Robot download is incomplete: missing {path}')


def fetch_archive(url,destination):
    print('Downloading official robot assets. This may take several minutes.',flush=True)
    with urllib.request.urlopen(url,timeout=120) as source,destination.open('wb') as out:
        total=0;reported=0
        while True:
            chunk=source.read(1024*1024)
            if not chunk:break
            out.write(chunk);total+=len(chunk)
            if total-reported>=10*1024*1024:
                print(f'Downloaded {total//(1024*1024)} MB...',flush=True);reported=total


def install_source(upstream,fetch=fetch_archive):
    """Download data into staging; never leave a partial folder as installed."""
    upstream=Path(upstream)
    if upstream.exists():check_source(upstream);return
    upstream.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='jumper-download-',dir=upstream.parent) as temp:
        staging=Path(temp);archive=staging/'source.zip'
        fetch(f'https://github.com/KingKongRobotics/jumper/archive/{COMMIT}.zip',archive)
        with zipfile.ZipFile(archive) as z:
            from pathlib import PurePosixPath
            import stat
            prefix=f'jumper-{COMMIT}'
            for info in z.infolist():
                name=PurePosixPath(info.filename)
                if (name.is_absolute() or '..' in name.parts or not name.parts or
                    name.parts[0]!=prefix or '\\' in info.filename or ':' in info.filename or
                    stat.S_ISLNK(info.external_attr>>16)):
                    raise RuntimeError('Unexpected or unsafe path in robot source archive')
            if z.testzip() is not None:raise RuntimeError('Robot archive download is damaged. Run setup again.')
            z.extractall(staging)
        source=staging/prefix
        (source/'.mission-source.json').write_text(json.dumps({'commit':COMMIT,'source':URL}))
        check_source(source)
        shutil.move(str(source),str(upstream))


def main():
    p=argparse.ArgumentParser();p.add_argument('--upstream',type=Path,default=ROOT.parent/'jumper-upstream')
    args=p.parse_args()
    if sys.version_info[:2] not in [(3,12),(3,13)]:raise SystemExit('Use 64-bit Python 3.12 or 3.13 and run setup.py again.')
    import struct
    if struct.calcsize('P')!=8:raise SystemExit('64-bit Python is required for the Windows robot runtime.')
    upstream=args.upstream.resolve()
    install_source(upstream)
    env=ROOT/'.venv';venv.EnvBuilder(with_pip=True).create(env)
    python=env/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    print('Installing Python dependencies...',flush=True)
    subprocess.run([str(python),'-m','pip','install','--only-binary=:all:','-r',str(ROOT/'requirements.txt')],check=True)
    subprocess.run([str(python),'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,check=True)
    (ROOT/'local-config.json').write_text(json.dumps({'upstream':str(upstream),'commit':COMMIT},indent=2))
    (ROOT/'.setup-complete').write_text('windows-launcher-v2\n')
    print('\nReady. Start with:')
    print(f'"{python}" server.py --upstream "{upstream}"')
    print('Then open http://127.0.0.1:8765 in Chrome or Edge.')


if __name__=='__main__':main()
