"""Local device benchmark; writes a shareable report without user paths or keys."""
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time

from server import VERSION

ROOT=Path(__file__).resolve().parent

def main():
    if sys.platform.startswith('linux') and not os.environ.get('DISPLAY'):os.environ.setdefault('MUJOCO_GL','egl')
    from mission.native import NativeJumper
    from mission.navigation import Maze
    config=json.loads((ROOT/'local-config.json').read_text()) if (ROOT/'local-config.json').exists() else {}
    upstream=config.get('upstream',str(ROOT.parent/'jumper-upstream'))
    print('Checking native physics without image rendering. This may take a minute on a slow device.',flush=True)
    robot=NativeJumper(upstream,Maze().obstacles(mutable=True));samples=[]
    started=time.perf_counter()
    try:
        for _ in range(200):
            began=time.perf_counter();robot.step(.02);samples.append((time.perf_counter()-began)*1000)
        elapsed=time.perf_counter()-started
        report=dict(schema='mission-device-check/1',version=VERSION,os=platform.system(),machine=platform.machine(),python=platform.python_version(),
            physics_step_ms=dict(median=round(statistics.median(samples),2),p95=round(sorted(samples)[189],2),maximum=round(max(samples),2)),
            unpaced_physics_speed=round(4/elapsed,2),fault=None,rendering='Browser 3D; Python rendering disabled during measurement',hardware_robot=False)
        (ROOT/'performance-report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2));print('\nSaved performance-report.json. Values above 1.0 for unpaced_physics_speed can keep up with real time.')
    finally:robot.close()
    return 0

if __name__=='__main__':raise SystemExit(main())
