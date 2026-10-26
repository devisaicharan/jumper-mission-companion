"""Release regressions for version detection, clocks and graphics isolation."""
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import Mock,patch
import urllib.request

import launch
from server import VERSION

class ReleaseTests(unittest.TestCase):
    def test_launcher_reuses_matching_server(self):
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.read.return_value=json.dumps({'version':VERSION,'backend':'native'}).encode()
        with patch.object(sys,'argv',['launch.py']),patch('launch.urllib.request.urlopen',return_value=response),patch('launch.subprocess.Popen') as spawn:
            self.assertEqual(launch.main(),0)
        spawn.assert_not_called()

    def test_launcher_rejects_old_server(self):
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.read.return_value=b'{"version":"0.1.4","backend":"native"}'
        with patch.object(sys,'argv',['launch.py']),patch('launch.urllib.request.urlopen',return_value=response),patch('launch.subprocess.Popen') as spawn:
            self.assertEqual(launch.main(),1)
        spawn.assert_not_called()

    def test_physics_slice_is_bounded_after_slow_frame(self):
        root=Path(__file__).resolve().parents[1];base='http://127.0.0.1:8773'
        # An injected 80 ms backend cost must not grow the next physics slice.
        code="import server,time\nbase=server.KinematicBackend.step\ndef step(self,seconds=.02):\n if seconds>.020001:raise RuntimeError('unbounded physics catchup')\n time.sleep(.08)\n return base(self,seconds)\nserver.KinematicBackend.step=step\nserver.main()"
        with subprocess.Popen([sys.executable,'-c',code,'--backend','preview','--port','8773'],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE) as process:
            try:
                for _ in range(60):
                    try:
                        with urllib.request.urlopen(base+'/api/config',timeout=1) as response:config=json.load(response)
                        break
                    except OSError:time.sleep(.05)
                else:self.fail('Server did not start')
                time.sleep(.4)
                req=urllib.request.Request(base+'/api/command',data=b'{"action":"stop"}',headers={'Origin':base,'X-Mission-Token':config['token'],'Content-Type':'application/json'})
                with urllib.request.urlopen(req,timeout=2) as response:result=json.load(response)
                self.assertIsNone(result['fault']);self.assertLess(result['robot']['sim_time'],result['time'])
            finally:process.terminate();process.communicate(timeout=5)
