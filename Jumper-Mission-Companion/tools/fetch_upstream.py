"""Fetch pinned upstream resources at image-build time, never on each request."""
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from setup import install_source

if __name__=='__main__':install_source(Path(os.environ.get('UPSTREAM_DIR','/opt/jumper-upstream')))
