"""Measured simulation acceptance; run separately from fast unit tests."""
import argparse
import json
import math
from pathlib import Path
from mission.native import NativeJumper
from mission.engine import Engine
from mission.navigation import Maze


def run(upstream):
    result={'environment':'native MuJoCo host; official Jumper model and compiled controller',
            'hardware_tested':False,'cases':[]}
    robot=NativeJumper(upstream)
    report=robot.fsm.check_reference((robot.bundle/'reference.json').read_text())
    result['controller_reference']={k:getattr(report,k) for k in ('frames','inferences','observation','target')}
    assert report.observation<1e-6 and report.target<1e-6
    reference=json.loads((robot.bundle/'reference.json').read_text())
    worst=0.;count=0
    for frame in reference['frames']:
        if 'obs' not in frame or 'act' not in frame or frame['act'] is None:continue
        import numpy as np
        session=robot.sessions[frame['mode']]
        output=session.run(None,{session.get_inputs()[0].name:np.array([frame['obs']],dtype=np.float32)})[0][0]
        worst=max(worst,float(np.max(np.abs(output-np.array(frame['act'])))));count+=1
    result['onnx_reference']={'frames':count,'worst_action_difference':worst}
    assert count>0 and worst<1e-5
    def advance(engine,seconds):
        peak_tilt=0.;peak_torque=0.
        for _ in range(round(seconds/.02)):
            engine.command('heartbeat');engine.tick(.02)
            s=engine.backend.state();peak_tilt=max(peak_tilt,s['tilt']);peak_torque=max(peak_torque,s['max_torque'])
            assert not engine.fault,engine.fault
        return {'peak_tilt_rad':peak_tilt,'peak_torque_nm':peak_torque}
    for symbol in ['wave','bow','paw','salute','celebrate']:
        robot.reset();e=Engine(robot);advance(e,2)
        e.command('voice',{'text':symbol})
        advance(e,.2)
        expected={'wave':'gesture_hello','bow':'gesture_bow','paw':'gesture_paw',
                  'salute':'gesture_salute','celebrate':'dance_crab'}[symbol]
        assert robot.state()['mode']==expected,(symbol,robot.state())
        metrics=advance(e,33)
        assert e.expressions.active is None and not e.expressions.queue
        assert any(x['kind']=='motion' and x['message']==f'done: {symbol}' for x in e.logs)
        result['cases'].append({'name':'voice-to-physics '+symbol,'passed':True,**metrics})
    robot.reset();e=Engine(robot);advance(e,2)
    e.command('celebrate');advance(e,2);e.command('stop');advance(e,2)
    assert robot.state()['mode']=='locomotion' and not e.expressions.queue
    result['cases'].append({'name':'cancel dance through native controller','passed':True})
    robot.reset();e=Engine(robot);e.command('configure_focus',{'focus':12,'rest':6})
    e.command('focus_start');advance(e,3);e.command('focus_pause');remaining=e.focus.remaining
    advance(e,2);assert e.focus.remaining==remaining
    e.command('focus_resume');advance(e,40)
    assert e.focus.sessions==1 and e.focus.state=='idle'
    result['cases'].append({'name':'focus pause/resume and one celebration in physics','passed':True})
    robot.reset();e=Engine(robot,seed=4);e.command('game_start');advance(e,15)
    assert e.game.state=='answering'
    answer=e.game.sequence[0];e.command(answer);advance(e,15)
    assert e.game.state=='won'
    e.command('game_next');advance(e,25)
    assert e.game.state=='answering' and len(e.game.sequence)==2
    wrong=next(s for s in e.game.symbols if s!=e.game.sequence[0]);e.command(wrong)
    assert e.game.state=='lost'
    result['cases'].append({'name':'two memory-game rounds, correct and wrong answers in physics','passed':True})
    robot.close()
    maze=Maze()
    for yaw in [0.,.6,-.8]:
        robot=NativeJumper(upstream,maze.obstacles());robot.data.qpos[3]=math.cos(yaw/2);robot.data.qpos[6]=math.sin(yaw/2)
        robot.mj.mj_forward(robot.model,robot.data)
        e=Engine(robot,maze);advance(e,2);e.command('mission_start')
        peak_tilt=0.;contacts=0
        for _ in range(6000):
            e.command('heartbeat');e.tick(.02)
            peak_tilt=max(peak_tilt,robot.state()['tilt'])
            for contact in robot.data.contact:
                a=robot.mj.mj_id2name(robot.model,robot.mj.mjtObj.mjOBJ_GEOM,contact.geom1) or ''
                b=robot.mj.mj_id2name(robot.model,robot.mj.mjtObj.mjOBJ_GEOM,contact.geom2) or ''
                if (a.startswith('wall_') or b.startswith('wall_')) and contact.dist<0:contacts+=1
            if e.nav.status!='running' or e.fault:break
        state=robot.state();error=math.dist((state['x'],state['y']),maze.world(maze.goal))
        record=dict(name=f'native maze yaw={yaw}',passed=e.nav.status=='complete' and not e.fault,
            elapsed_sim_seconds=state['sim_time'],goal_error_m=error,peak_tilt_rad=peak_tilt,
            wall_penetrating_contact_samples=contacts,status=e.nav.status,fault=e.fault)
        result['cases'].append(record)
        assert record['passed'] and error<.1,record
        robot.close()
    maze=Maze();robot=NativeJumper(upstream,maze.obstacles(mutable=True));e=Engine(robot,maze)
    advance(e,2);e.command('mission_start');advance(e,1)
    obstacle=tuple(e.nav.path[3]);e.command('toggle_obstacle',{'x':obstacle[0],'y':obstacle[1]})
    gid=robot.obstacle_geoms[obstacle]
    assert robot.model.geom_contype[gid]==1 and obstacle not in e.nav.path and e.nav.replans==1
    for _ in range(6000):
        e.command('heartbeat');e.tick(.02)
        if e.nav.status!='running' or e.fault:break
    dynamic={'name':'native dynamic obstacle activation and route replanning',
             'passed':e.nav.status=='complete' and not e.fault,
             'replans':e.nav.replans,'inserted_cell':obstacle,'status':e.nav.status}
    result['cases'].append(dynamic);assert dynamic['passed'],dynamic
    robot.close()
    result['passed']=all(c['passed'] for c in result['cases'])
    Path('docs/native-results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--upstream',default='../jumper-upstream')
    run(p.parse_args().upstream)
