"""The hosted model cache must preserve physics and reject stale scenes."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import mujoco
import numpy as np

from mission.native import load_model


class NativeCacheTests(unittest.TestCase):
    XML = '<mujoco><worldbody><body pos="0 0 1"><freejoint/><geom type="sphere" size="0.1"/></body></worldbody></mujoco>'

    def test_cached_model_preserves_physics_without_recompiling(self):
        with tempfile.TemporaryDirectory() as directory:
            compiled = load_model(mujoco, self.XML, directory, build_cache=True)
            # A cache hit must not invoke the memory-heavy XML compiler.
            runtime = SimpleNamespace(__version__=mujoco.__version__, MjModel=SimpleNamespace(
                from_binary_path=mujoco.MjModel.from_binary_path,
                from_xml_string=Mock(side_effect=AssertionError('runtime compilation'))))
            cached = load_model(runtime, self.XML, directory)
            a, b = mujoco.MjData(compiled), mujoco.MjData(cached)
            for _ in range(100):
                mujoco.mj_step(compiled, a)
                mujoco.mj_step(cached, b)
            np.testing.assert_array_equal(a.qpos, b.qpos)
            np.testing.assert_array_equal(a.qvel, b.qvel)
            self.assertEqual(len(list(Path(directory).glob('*.mjb'))), 1)

    def test_changed_scene_or_version_requires_rebuild(self):
        with tempfile.TemporaryDirectory() as directory:
            load_model(mujoco, self.XML, directory, build_cache=True)
            with self.assertRaisesRegex(RuntimeError, 'Rebuild'):
                load_model(mujoco, self.XML.replace('0.1', '0.2'), directory)
            with patch.object(mujoco, '__version__', 'incompatible'):
                with self.assertRaisesRegex(RuntimeError, 'Rebuild'):
                    load_model(mujoco, self.XML, directory)

    def test_missing_cache_fails_without_compilation(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, 'Rebuild'):
                load_model(mujoco, self.XML, directory)

