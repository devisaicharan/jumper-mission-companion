"""Measure local HTTP acknowledgement latency with native rendering under load."""
import concurrent.futures
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import urllib.request

root=Path(__file__).resolve().parents[1]
base='http://127.0.0.1:8771'
def request(path, data=None, token=None):
    headers={'Origin':base}
    if token: headers.update({'X-Mission-Token':token,'Content-Type':'application/json'})
    req=urllib.request.Request(base+path, data=data, headers=headers)
    with urllib.request.urlopen(req,timeout=15) as response: return response.read()

def main():
    view=os.environ.get('MISSION_TEST_VIEW','browser')
    args=[sys.executable,'server.py','--port','8771','--view',view]
    slow=os.environ.get('MISSION_TEST_SLOW_RENDER')=='1'
    if slow:
        code="from mission.native import NativeJumper; import time; original=NativeJumper.finish_render\ndef slow(self):\n time.sleep(.7)\n return original(self)\nNativeJumper.finish_render=slow\nimport server; server.main()"
        args=[sys.executable,'-c',code,'--port','8771','--view','image']
    server=subprocess.Popen(args,cwd=root,stdout=subprocess.DEVNULL)
    try:
        for _ in range(300):
            try: config=json.loads(request('/api/config'));break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Server startup failed')
        time.sleep(2)
        samples=[]
        def command(action):
            start=time.perf_counter()
            result=json.loads(request('/api/command',json.dumps({'action':action}).encode(),config['token']))
            return (time.perf_counter()-start)*1000,result
        def frames():
            for _ in range(100):
                try: request('/api/frame')
                except OSError:pass
                time.sleep(.05)
        start_state=json.loads(request('/api/state'));start=time.monotonic()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            future=pool.submit(frames)
            for i in range(100):
                latency,result=command('stop' if i%10==0 else 'heartbeat')
                assert result['fault'] is None,result['fault']
                samples.append(latency);time.sleep(.03)
            future.result()
        end=json.loads(request('/api/state'));wall=time.monotonic()-start
        ordered=sorted(samples)
        report=dict(samples=len(samples),ack_ms=dict(median=round(statistics.median(samples),2),p95=round(ordered[94],2),max=round(max(samples),2)),simulated_seconds=round(end['robot']['sim_time']-start_state['robot']['sim_time'],3),wall_seconds=round(wall,3),fault=end['fault'])
        report['artificial_render_delay_ms']=700 if slow else 0
        report['performance']=end.get('performance',{})
        report['view']='image' if slow else view
        if slow:assert report['ack_ms']['p95']<500,report
        output=Path(sys.argv[1]) if len(sys.argv)>1 else root/'docs/latency-results.json'
        output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
    finally:
        server.terminate()
        try:server.wait(timeout=5)
        except subprocess.TimeoutExpired:server.kill();server.wait()
if __name__=='__main__':main()
