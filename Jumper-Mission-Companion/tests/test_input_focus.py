import unittest
from mission.engine import Engine,KinematicBackend
from mission.perception import GestureGate,parse_voice,gesture
from mission.activities import Focus
from tests.test_core import landmarks

class InputFocusTests(unittest.TestCase):
    def test_short_projected_straight_fingers_still_form_v(self):
        points=landmarks([1,1,0,0])
        for tip,dip in [(8,7),(12,11)]:points[tip]['y']=.35;points[dip]['y']=.375
        self.assertEqual(gesture(points),'wave')

    def test_short_tracking_gap_preserves_deliberate_hold(self):
        g=GestureGate();g.update('wave',0);g.update('wave',.2)
        self.assertIsNone(g.update('unknown',.3))
        self.assertIsNone(g.update('wave',.4))
        self.assertEqual(g.update('wave',.5),'wave')

    def test_low_confidence_needs_current_confirmation(self):
        e=Engine(KinematicBackend());e.command('voice',{'text':'wave','confidence':0})
        self.assertEqual(e.voice_feedback['phase'],'confirm');self.assertFalse(e.expressions.queue)
        old=e.voice_feedback['id'];e.command('voice',{'text':'bow','confidence':0})
        with self.assertRaises(ValueError):e.command('voice_confirm',{'id':old})
        e.command('voice_confirm',{'id':e.voice_feedback['id']});e.tick(.02)
        self.assertEqual(e.backend.mode,'bow')

    def test_stop_invalidates_pending_voice(self):
        e=Engine(KinematicBackend());e.command('voice',{'text':'wave','confidence':0});pending=e.voice_feedback['id']
        e.command('stop')
        with self.assertRaises(ValueError):e.command('voice_confirm',{'id':pending})

    def test_speech_alternative_can_supply_exact_command(self):
        e=Engine(KinematicBackend());e.command('voice',{'alternatives':[{'text':'waif','confidence':.95},{'text':'wave','confidence':.9}]});e.tick(.02)
        self.assertEqual(e.backend.mode,'wave');self.assertEqual(e.voice_feedback['heard'],'wave')

    def test_unmatched_speech_explains_without_moving(self):
        e=Engine(KinematicBackend());e.command('voice',{'text':'explain the maze please'})
        self.assertEqual(e.voice_feedback['phase'],'unmatched');self.assertFalse(e.expressions.queue)

    def test_polite_commands_stay_exact(self):
        self.assertEqual(parse_voice('Hey, hi.'),'wave')
        self.assertEqual(parse_voice('Jumper please wave your hand please'),'wave')
        for phrase in ['please do not wave','do not start focus','tell me how to dance']:
            self.assertIsNone(parse_voice(phrase))

    def test_gesture_reaches_action_and_palm_keeps_camera(self):
        e=Engine(KinematicBackend());e.command('camera_enable',{'enabled':True})
        for _ in range(12):e.command('landmarks',{'points':landmarks([1,1,0,0])});e.command('heartbeat');e.tick(.05)
        self.assertEqual(e.backend.mode,'wave');self.assertEqual(e.gesture_feedback['action'],'wave')
        for _ in range(5):e.command('landmarks',{'points':landmarks([1,1,1,1])});e.command('heartbeat');e.tick(.05)
        self.assertEqual(e.backend.mode,'locomotion');self.assertTrue(e.camera_enabled)

    def test_focus_start_applies_task_and_durations(self):
        e=Engine(KinematicBackend());e.command('focus_start',{'focus':12,'rest':6,'task':'Revise OS'})
        self.assertEqual(e.focus.duration,12);self.assertEqual(e.focus.task,'Revise OS')
        with self.assertRaises(ValueError):e.command('focus_start')
        self.assertEqual(e.focus.state,'focus')
        e.command('focus_stop');self.assertEqual(e.activity,'manual');self.assertEqual(e.focus.last_event,'cancelled')

    def test_break_pause_resume_and_history(self):
        f=Focus();f.configure(2,3,'Read one page');f.command('start',0)
        self.assertEqual(f.tick(2),'celebrate');self.assertEqual(f.sessions,1)
        f.command('pause',3);self.assertEqual(f.paused_phase,'break');self.assertIsNone(f.tick(30))
        f.command('resume',30);self.assertEqual(f.state,'break');self.assertEqual(f.tick(32),'bow')
        self.assertEqual(f.last_event,'break_complete');self.assertEqual(f.history[0]['task'],'Read one page')
        self.assertEqual(f.sessions,1)

    def test_skip_break_does_not_start_another_focus(self):
        e=Engine(KinematicBackend());e.command('focus_start',{'focus':1,'rest':5})
        for _ in range(60):e.command('heartbeat');e.tick(.02)
        e.command('focus_skip_break');self.assertEqual(e.focus.state,'idle');self.assertEqual(e.activity,'manual')

    def test_invalid_task_does_not_partially_change_configuration(self):
        f=Focus()
        with self.assertRaises(ValueError):f.configure(10,2,'x'*121)
        self.assertEqual(f.duration,1500)

    def test_focus_continues_away_without_robot_rewards(self):
        e=Engine(KinematicBackend());e.command('focus_start',{'focus':1,'rest':1})
        e.command('ui_hidden')
        for _ in range(150):e.tick(.02)
        self.assertEqual(e.focus.sessions,1);self.assertEqual(e.focus.last_event,'break_complete')
        self.assertIsNone(e.expressions.active);self.assertFalse(e.expressions.queue)
        self.assertEqual(e.backend.mode,'locomotion')

    def test_missing_heartbeat_preserves_only_focus_timer(self):
        e=Engine(KinematicBackend());e.command('focus_start',{'focus':20,'rest':5})
        for _ in range(150):e.tick(.02)
        self.assertTrue(e.background_focus);self.assertEqual(e.focus.state,'focus');self.assertFalse(e.expressions.queue)
        e.command('stop');self.assertEqual(e.focus.state,'idle')
