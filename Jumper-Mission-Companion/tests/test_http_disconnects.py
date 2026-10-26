"""Dropped response headers/bodies must never become simulation faults."""
import io
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import Mock,patch
import urllib.request

from server import LocalHandler

class DisconnectTests(unittest.TestCase):
    def handler(self):
        h=object.__new__(LocalHandler)
        h.send_response=Mock();h.send_header=Mock();h.end_headers=Mock()
        h.wfile=io.BytesIO();h.close_connection=False
        return h

    def test_header_disconnects_are_contained(self):
        for error in (ConnectionAbortedError(10053,'Windows connection aborted'),
                      ConnectionResetError(),BrokenPipeError(),TimeoutError()):
            with self.subTest(error=type(error).__name__):
                h=self.handler();h.end_headers.side_effect=error
                h.send(200,{'ok':True})
                self.assertTrue(h.close_connection)

    def test_body_disconnect_is_contained(self):
        h=self.handler();h.wfile=Mock();h.wfile.write.side_effect=ConnectionAbortedError(10053,'aborted')
        h.send(200,{'ok':True});self.assertTrue(h.close_connection)

    def test_request_disconnect_is_contained(self):
        h=self.handler()
        with patch('http.server.BaseHTTPRequestHandler.handle',side_effect=ConnectionAbortedError(10053,'aborted')):
            h.handle()
        self.assertTrue(h.close_connection)

    def test_aborted_command_response_does_not_fault_engine(self):
        root=Path(__file__).resolve().parents[1];base='http://127.0.0.1:8772'
        code="import server\noriginal=server.LocalHandler.end_headers\ndef abort_once(self):\n if self.path=='/api/command' and not getattr(self.server,'aborted',False):\n  self.server.aborted=True\n  raise ConnectionAbortedError(10053,'injected Windows disconnect')\n return original(self)\nserver.LocalHandler.end_headers=abort_once\nserver.main()"
        with subprocess.Popen([sys.executable,'-c',code,'--backend','preview','--port','8772'],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE) as process:
            try:
                for _ in range(80):
                    try:
                        with urllib.request.urlopen(base+'/api/config',timeout=1) as response:config=json.load(response)
                        break
                    except OSError:time.sleep(.05)
                else:self.fail('Server did not start')
                def command(action):
                    req=urllib.request.Request(base+'/api/command',data=json.dumps({'action':action}).encode(),headers={'Origin':base,'X-Mission-Token':config['token'],'Content-Type':'application/json'})
                    with urllib.request.urlopen(req,timeout=2) as response:return json.load(response)
                with self.assertRaises(OSError):command('wave')
                result=command('stop')
                self.assertIsNone(result['fault']);self.assertEqual(result['expression']['queued'],0)
            finally:
                process.terminate();stdout,stderr=process.communicate(timeout=5)
            self.assertNotIn(b'Traceback',stderr)
