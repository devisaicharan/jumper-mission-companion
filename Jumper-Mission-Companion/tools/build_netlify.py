"""Prepare optional Netlify frontend; Render remains the simulation backend."""
import os
from pathlib import Path
import shutil
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]


def build(value,destination=None):
    p=urlsplit(value)
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.path not in ('','/') or p.query or p.fragment:
        raise ValueError('Set RENDER_BACKEND_URL to the exact HTTPS Render origin, without a path')
    url=f'https://{p.netloc}'
    destination=Path(destination or ROOT/'netlify-dist')
    if destination.exists():shutil.rmtree(destination)
    shutil.copytree(ROOT/'static',destination)
    (destination/'_redirects').write_text(f'/api/* {url}/api/:splat 200\n')
    return destination


if __name__=='__main__':
    target=build(os.environ.get('RENDER_BACKEND_URL',''))
    print(f'Netlify frontend prepared in {target.name}; native backend remains on Render.')
