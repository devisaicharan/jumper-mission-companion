"""State ordering must remain correct during rapid commands and simulation reset."""
import unittest
from mission.engine import Engine,KinematicBackend

class ReactivityTests(unittest.TestCase):
    def test_reset_keeps_revision_monotonic(self):
        e=Engine(KinematicBackend())
        e.tick(.02);before=e.snapshot()
        e.command('reset');after=e.snapshot()
        self.assertGreater(after['revision'],before['revision'])
        self.assertLess(after['robot']['sim_time'],before['robot']['sim_time'])

    def test_stop_cancels_a_rapid_command_burst(self):
        e=Engine(KinematicBackend())
        for action in ('wave','celebrate','left','game_start','stop'):
            e.command(action)
        e.tick(.02)
        self.assertEqual(e.activity,'manual')
        self.assertFalse(e.expressions.queue)
        self.assertIsNone(e.expressions.active)
        self.assertEqual(e.backend.control,(0.,0.,0.))

    def test_heartbeat_does_not_change_activity(self):
        e=Engine(KinematicBackend());e.command('focus_start')
        for _ in range(20):e.command('heartbeat');e.tick(.02)
        self.assertEqual(e.activity,'focus')
        self.assertEqual(e.focus.state,'focus')
