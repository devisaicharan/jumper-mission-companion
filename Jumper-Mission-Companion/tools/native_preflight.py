"""Fail the image build if official native assets or ABI cannot load."""
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mission.native import NativeJumper
from mission.navigation import Maze

if __name__=='__main__':
    robot=NativeJumper(os.environ.get('UPSTREAM_DIR',str(Path(__file__).resolve().parents[2]/'jumper-upstream')),Maze().obstacles(mutable=True))
    try:
        robot.step(.02)
        assert robot.state()['backend']=='mujoco-official-jumper'
        assert len(robot.scene_description()['geoms'])>0
        print('Native model/controller/ONNX load and headless physics preflight passed.')
    finally:robot.close()
