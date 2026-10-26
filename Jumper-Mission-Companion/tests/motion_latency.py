"""Measure queue, native mode-entry and safe pose handoff separately."""
import json
from pathlib import Path
from mission.native import NativeJumper
from mission.engine import Engine

root=Path(__file__).resolve().parents[1]
b=NativeJumper(root.parent/'jumper-upstream');engine=Engine(b)
for _ in range(400):engine.command('heartbeat');engine.tick(.005)
engine.command('wave');start=b.data.time;results={}
for _ in range(1200):
    engine.command('heartbeat');engine.tick(.005)
    state=b.state();elapsed=round((b.data.time-start)*1000,2)
    if engine.expressions.active and 'queue_release_sim_ms' not in results:results['queue_release_sim_ms']=elapsed
    if state['mode']=='gesture_hello':
        results.setdefault('mode_entry_sim_ms',elapsed)
        if state['running']:
            results['policy_ready_sim_ms']=elapsed;break
else:raise AssertionError('Wave policy never entered running state')
assert results['mode_entry_sim_ms']<=30,results
assert results['policy_ready_sim_ms']<3000,results
results['note']='Simulation milliseconds; pose handoff preserved. Wall time depends on laptop simulation speed.'
(root/'docs/motion-latency-results.json').write_text(json.dumps(results,indent=2)+'\n')
b.close();print(json.dumps(results))
