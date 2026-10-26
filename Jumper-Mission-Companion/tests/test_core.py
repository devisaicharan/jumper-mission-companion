import math
import random
import unittest
from collections import deque
from mission.perception import gesture, GestureGate, parse_voice
from mission.navigation import Maze, Navigator
from mission.activities import Focus, MemoryGame, Expressions
from mission.engine import Engine, KinematicBackend


def landmarks(extended):
    p=[dict(x=0.5,y=0.8,z=0.) for _ in range(21)]
    for i,(mcp,pip,dip,tip) in enumerate([(5,6,7,8),(9,10,11,12),(13,14,15,16),(17,18,19,20)]):
        x=0.35+i*0.1
        for idx,y in zip((mcp,pip,dip,tip),(0.55,0.4,0.3,0.15) if extended[i] else (0.55,0.4,0.5,0.6)):
            p[idx]=dict(x=x,y=y,z=0.)
    return p


class PerceptionTests(unittest.TestCase):
    def test_landmark_classes_and_rotation(self):
        for fingers,label in [([1,1,1,1],'stop'),([0,0,0,0],'quiet'),([1,1,0,0],'wave')]:
            p=landmarks(fingers)
            self.assertEqual(gesture(p),label)
            for v in p:v['x'],v['y']=v['y']*0.5+0.1,-v['x']*0.5+0.8
            self.assertEqual(gesture(p),label)
    def test_points_reject_malformed(self):
        for p in [None,[],[{}]*21,[dict(x=math.nan,y=0)]*21]:
            self.assertEqual(gesture(p),'unknown')
    def test_dwell_release_and_unknown_gap(self):
        g=GestureGate()
        self.assertIsNone(g.update('wave',0))
        self.assertIsNone(g.update('wave',0.2))
        self.assertEqual(g.update('wave',0.5),'wave')
        self.assertIsNone(g.update('wave',4))
        g.update('unknown',5);g.update('unknown',5.3)
        g.update('wave',6)
        self.assertEqual(g.update('wave',6.5),'wave')
    def test_stop_has_shorter_dwell_but_no_repeats(self):
        g=GestureGate();g.update('stop',0)
        self.assertEqual(g.update('stop',0.13),'stop')
        self.assertIsNone(g.update('stop',1))
    def test_gate_rejects_time_reversal(self):
        g=GestureGate();g.update('wave',1)
        with self.assertRaises(ValueError):g.update('wave',0)
    def test_voice_closed_vocabulary(self):
        self.assertEqual(parse_voice('Jumper, say hello!'),'wave')
        self.assertEqual(parse_voice('hey jumper start mission'),'mission_start')
        for phrase in ['do not stop','explain how to solve maze','start mission and jump','jump']:
            self.assertIsNone(parse_voice(phrase))
    def test_voice_confidence_and_unknown(self):
        self.assertIsNone(parse_voice('start mission',0.6))
        self.assertEqual(parse_voice('stop',0.4),'stop')
        self.assertIsNone(parse_voice('stop',math.nan))


class NavigationTests(unittest.TestCase):
    def test_route_is_contiguous_and_clear(self):
        maze=Maze();path=maze.plan((1,1))
        self.assertEqual(path[0],(1,1));self.assertEqual(path[-1],maze.goal)
        for a,b in zip(path,path[1:]):
            self.assertEqual(abs(a[0]-b[0])+abs(a[1]-b[1]),1)
            self.assertTrue(maze.segment_clear(maze.world(a),maze.world(b)))
    def test_unreachable_and_blocked_goal(self):
        m=Maze(['#####','#.#.#','#####'])
        self.assertEqual(m.plan((1,1),(3,1)),[])
        self.assertEqual(m.plan((0,0)),[])
    def test_astar_matches_bfs_over_random_maps(self):
        rng=random.Random(82)
        for _ in range(60):
            rows=['#######']+['#'+''.join('#' if rng.random()<.2 else '.' for _ in range(5))+'#' for _ in range(5)]+['#######']
            m=Maze(rows);m.blocked.discard((1,1));m.blocked.discard((5,5))
            q=deque([((1,1),0)]);seen={(1,1)};answer=None
            while q:
                cell,n=q.popleft()
                if cell==(5,5):answer=n;break
                for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                    p=cell[0]+dx,cell[1]+dy
                    if p not in seen and m.traversable(p):seen.add(p);q.append((p,n+1))
            route=m.plan((1,1),(5,5))
            self.assertEqual(len(route)-1 if route else None,answer)
    def test_dynamic_replan(self):
        m=Maze();n=Navigator(m);p={'x':0.,'y':0.,'yaw':0.}
        n.start(p,0);old=list(n.path);m.blocked.add(old[2]);n.replan(p,1)
        self.assertEqual(n.replans,1);self.assertNotIn(old[2],n.path)
    def test_stalled_robot_stops(self):
        m=Maze();n=Navigator(m);p={'x':0.,'y':0.,'yaw':0.}
        n.start(p,0);n.tick(p,0)
        self.assertEqual(n.tick(p,13),(0.,0.,0.));self.assertEqual(n.status,'stalled')
    def test_body_frame_rotation(self):
        m=Maze(['#####','#...#','#...#','#####']);n=Navigator(m)
        n.path=[(2,1)];n.status='running'
        vx,vy,_=n.tick({'x':0,'y':0,'yaw':math.pi/2},0)
        self.assertAlmostEqual(vx,0,places=6);self.assertLess(vy,0)
    def test_disc_clearance(self):
        m=Maze();self.assertTrue(m.clear(0,0));self.assertFalse(m.clear(-0.1,0))


class ActivityTests(unittest.TestCase):
    def test_focus_pause_resume(self):
        f=Focus();f.configure(12,6);f.command('start',1);f.command('pause',5)
        self.assertIsNone(f.tick(100));f.command('resume',100)
        self.assertIsNone(f.tick(107));self.assertEqual(f.tick(108),'celebrate')
        self.assertIsNone(f.tick(109));self.assertEqual(f.tick(114),'bow')
        self.assertEqual(f.state,'idle');self.assertEqual(f.sessions,1)
    def test_stop_clears_timer(self):
        f=Focus();f.configure(1,1);f.command('start',0);f.command('stop',.5)
        self.assertIsNone(f.tick(5))
    def test_focus_configuration(self):
        f=Focus()
        for v in [0,-1,math.inf,math.nan,None]:
            with self.assertRaises(ValueError):f.configure(v,1)
    def test_game_round_and_wrong_answer(self):
        g=MemoryGame(1);seq=g.start();self.assertEqual(g.state,'showing')
        with self.assertRaises(ValueError):g.answer(seq[0])
        g.ready();self.assertTrue(g.answer(seq[0]));self.assertEqual(g.state,'won')
        seq=g.next_round();self.assertEqual(len(seq),2);g.ready()
        wrong=next(s for s in g.symbols if s!=seq[0]);self.assertFalse(g.answer(wrong))
        self.assertEqual(g.state,'lost');self.assertEqual(len(g.start()),1)
    def test_game_snapshot_hides_answer(self):
        g=MemoryGame(1);g.start();g.ready();self.assertNotIn('sequence',g.snapshot())
    def test_expression_ack_and_timeout(self):
        e=Expressions();b=KinematicBackend();e.enqueue(['wave'],'friendly')
        self.assertEqual(e.tick(b,0),('started','wave'));e.tick(b,.1)
        b.step(1.3);self.assertEqual(e.tick(b,1.3),('done','wave'))
        e.enqueue(['bow'],'thanks');e.tick(b,2)
        b.mode='stuck';self.assertEqual(e.tick(b,38)[0],'fault')
    def test_queue_bound(self):
        with self.assertRaises(ValueError):Expressions().enqueue(['wave']*25,'test')


class EngineTests(unittest.TestCase):
    def engine(self):return Engine(KinematicBackend(),seed=4)
    def run_for(self,e,seconds):
        for _ in range(round(seconds/.02)):
            e.command('heartbeat');e.tick(.02)
    def test_voice_drives_actual_controller(self):
        e=self.engine();e.command('voice',{'text':'Jumper say hello'})
        self.run_for(e,.2);self.assertEqual(e.backend.mode,'wave')
    def test_stop_preempts_every_activity(self):
        for action in ['mission_start','focus_start','game_start','celebrate','left']:
            e=self.engine();e.command(action);self.run_for(e,.5);e.command('stop')
            self.run_for(e,3)
            self.assertEqual(e.activity,'manual');self.assertEqual(e.focus.state,'idle')
            self.assertEqual(e.game.state,'idle');self.assertEqual(e.backend.control,(0.,0.,0.))
            self.assertFalse(e.expressions.queue)
    def test_ui_watchdog(self):
        e=self.engine();e.command('mission_start')
        for _ in range(110):e.tick(.02)
        self.assertEqual(e.activity,'manual')
        self.assertTrue(any(l['kind']=='watchdog' for l in e.logs))
    def test_game_only_unlocks_after_motion_ack(self):
        e=self.engine();e.command('game_start');self.run_for(e,.5)
        self.assertEqual(e.game.state,'showing')
        self.run_for(e,2);self.assertEqual(e.game.state,'answering')
        e.command(e.game.sequence[0]);self.assertEqual(e.game.state,'won')
    def test_camera_disabled_and_release_stop(self):
        e=self.engine();e.command('landmarks',{'points':landmarks([1,1,0,0])})
        self.assertFalse(e.expressions.queue)
        e.command('camera_enable',{'enabled':True});e.command('left',source='gesture')
        self.run_for(e,.8);self.assertEqual(e.backend.control,(0.,0.,0.))
    def test_full_maze_preview(self):
        e=self.engine();e.command('mission_start')
        self.run_for(e,120)
        self.assertEqual(e.nav.status,'complete')
        self.assertLess(math.dist((e.backend.x,e.backend.y),e.maze.world(e.maze.goal)),.1)
    def test_invalid_time_and_command(self):
        e=self.engine()
        with self.assertRaises(ValueError):e.tick(math.nan)
        with self.assertRaises(ValueError):e.command('fly')
    def test_obstacle_cannot_be_added_inside_robot_envelope(self):
        e=self.engine();e.backend.x=.28
        with self.assertRaises(ValueError):e.command('toggle_obstacle',{'x':2,'y':1})
        self.assertNotIn((2,1),e.maze.blocked)
    def test_reset_restores_default_obstacles(self):
        e=self.engine();e.command('toggle_obstacle',{'x':2,'y':1})
        self.assertIn((2,1),e.maze.blocked);e.command('reset')
        self.assertNotIn((2,1),e.maze.blocked)
    def test_quiet_cancels_game_demonstration(self):
        e=self.engine();e.command('game_start');e.command('quiet');self.run_for(e,2)
        self.assertEqual(e.game.state,'idle')
    def test_conflicting_activities_cancel_prior_owner(self):
        e=self.engine();e.command('focus_start');e.command('mission_start')
        self.assertEqual(e.focus.state,'idle');self.assertEqual(e.activity,'mission')


if __name__=='__main__':unittest.main()
