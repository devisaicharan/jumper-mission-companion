"""Run the local Mission Companion dashboard. No publishing or cloud account."""
import argparse
import io
import gzip
import json
import os
from pathlib import Path
import secrets
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit
from mission.engine import Engine, KinematicBackend
from mission.navigation import Maze

ROOT=Path(__file__).resolve().parent
VERSION='1.3.0'


class LocalHandler(BaseHTTPRequestHandler):
    """A browser disconnect is a transport event, never a robot fault."""
    def handle(self):
        try:super().handle()
        except (ConnectionError,TimeoutError):self.close_connection=True

    def send(self,status,body,kind='application/json',headers=None):
        if isinstance(body,(dict,list)):body=json.dumps(body,allow_nan=False).encode()
        if isinstance(body,str):body=body.encode()
        try:
            self.send_response(status)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            for key,value in (headers or {}).items():self.send_header(key,value)
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionError,TimeoutError):
            self.close_connection=True


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--backend',choices=['native','preview'],default='native')
    parser.add_argument('--upstream',default=str(ROOT.parent/'jumper-upstream'))
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--no-render',action='store_true')
    parser.add_argument('--view',choices=['browser','map','image'],default='browser')
    args=parser.parse_args()
    maze=Maze()
    if args.backend=='native':
        import sys
        if sys.platform.startswith('linux') and not os.environ.get('DISPLAY'):
            os.environ.setdefault('MUJOCO_GL','egl')
        from mission.native import NativeJumper
        backend=NativeJumper(args.upstream,obstacles=maze.obstacles(mutable=True))
    else:
        backend=KinematicBackend()
    engine=Engine(backend,maze)
    scene=gzip.compress(json.dumps(backend.scene_description(),separators=(',',':')).encode(),compresslevel=5) if args.backend=='native' else None
    view=[args.view]
    engine.performance.update(view_mode='Browser 3D' if args.view=='browser' else args.view.title(),version=VERSION)
    lock=threading.RLock()
    shutdown=threading.Event()
    token=secrets.token_urlsafe(24)
    picture=[None]
    render_fault=[None]
    frame_ready=threading.Condition()
    frame_number=[0]
    render_interval=[1/12]

    def loop():
        last=time.monotonic();sample_wall=last;sample_sim=backend.state()['sim_time']
        while not shutdown.is_set():
            began=time.monotonic();elapsed=began-last;last=began
            # A slow laptop must yield between short physics slices; catching up
            # 250 ms of physics under this lock made Stop wait hundreds of ms.
            dt=min(0.02,max(0.005,elapsed))
            try:
                with lock:
                    engine.now+=max(0,elapsed-dt)
                    if elapsed>2:
                        # Resume from laptop sleep/long stalls without replaying
                        # stale motion requests or silently losing timer minutes.
                        engine.quiet_background()
                        engine._event('watchdog','Control loop paused; robot motion cancelled')
                    engine.tick(dt)
                    engine.performance['control_step_ms']=round((time.monotonic()-began)*1000,1)
                    engine.performance['view_mode']=('Browser 3D' if view[0]=='browser' else
                        '2D map' if view[0]=='map' else ('Image · Eco' if render_interval[0]>.1 else 'Image · Balanced'))
                    if began-sample_wall>=1:
                        sim=backend.state()['sim_time']
                        if sim>=sample_sim:
                            factor=(sim-sample_sim)/(began-sample_wall)
                            engine.performance['real_time_factor']=round(factor,2)
                            if factor<.8:
                                render_interval[0]=max(.25,min(1,engine.performance.get('render_ms',125)/500))
                            elif factor>.95:render_interval[0]=1/12
                        sample_wall=began;sample_sim=sim
            except Exception as exc:
                with lock:
                    engine.stop();engine.fault=f'{type(exc).__name__}: {exc}'
                    engine._event('fault',engine.fault)
                    print(f'Simulation error: {engine.fault}',flush=True)
                # Renderer failures are surfaced, never substituted by a fake image.
                render_fault[0]=str(exc)
                shutdown.set()
            shutdown.wait(max(0.001,0.02-(time.monotonic()-began)))

    def render_loop():
        # One owner for the GL context. Only scene preparation shares the physics
        # lock; slow GPU readback and JPEG compression never hold up commands.
        from PIL import Image
        try:
            while not shutdown.is_set():
                if view[0]!='image':
                    shutdown.wait(.1);continue
                began=time.monotonic()
                with lock:backend.capture_render_state()
                backend.prepare_render(width=480,height=320,eco=render_interval[0]>.1,capture=False)
                pixels=backend.finish_render()
                out=io.BytesIO()
                Image.fromarray(pixels).save(out,format='JPEG',quality=76)
                with frame_ready:
                    picture[0]=out.getvalue();frame_number[0]+=1;frame_ready.notify_all()
                with lock:
                    engine.performance['render_ms']=round((time.monotonic()-began)*1000,1)
                    engine.performance['frame_number']=frame_number[0]
                shutdown.wait(max(0,render_interval[0]-(time.monotonic()-began)))
        except Exception as exc:
            render_fault[0]=f'{type(exc).__name__}: {exc}'
            print(f'Render error (controls remain available): {render_fault[0]}',flush=True)
        finally:backend.close()

    class Handler(LocalHandler):
        def log_message(self,*_args): pass
        def do_GET(self):
            path=urlsplit(self.path).path
            if path=='/api/scene':
                if scene is None:return self.send(404,{'error':'No native scene in preview mode'})
                return self.send(200,scene,'application/json',{'Content-Encoding':'gzip'})
            if path=='/api/stream':
                if args.backend!='native' or args.no_render or view[0]!='image':
                    return self.send(503,{'error':'Native rendering is disabled'})
                return self.stream_frames()
            if path=='/api/state':
                with lock:
                    result=engine.snapshot();result['render_error']=render_fault[0] if view[0]=='image' else None
                return self.send(200,result)
            if path=='/api/config':return self.send(200,{'token':token,'backend':args.backend,'version':VERSION,'view':view[0],'image_available':not args.no_render})
            if path=='/api/frame':
                if picture[0] is None:return self.send(503,{'error':render_fault[0] or 'Frame not ready'})
                return self.send(200,picture[0],'image/jpeg')
            file=(ROOT/'static'/('index.html' if path=='/' else path.lstrip('/'))).resolve()
            if not file.is_relative_to(ROOT/'static') or not file.is_file():
                return self.send(404,{'error':'Not found'})
            kinds={'.html':'text/html; charset=utf-8','.css':'text/css',
                   '.js':'text/javascript','.mjs':'text/javascript','.wasm':'application/wasm',
                   '.task':'application/octet-stream','.json':'application/json'}
            self.send(200,file.read_bytes(),kinds.get(file.suffix,'application/octet-stream'))
        def stream_frames(self):
            # A single browser image stream removes fetch/decode idle gaps.
            try:
                self.send_response(200)
                self.send_header('Content-Type','multipart/x-mixed-replace; boundary=missionframe')
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.end_headers()
                previous=0
                while not shutdown.is_set() and not render_fault[0] and view[0]=='image':
                    with frame_ready:
                        frame_ready.wait_for(lambda:frame_number[0]!=previous or shutdown.is_set(),timeout=1)
                        if picture[0] is None or frame_number[0]==previous:continue
                        frame=picture[0];previous=frame_number[0]
                    self.wfile.write(b'--missionframe\r\nContent-Type: image/jpeg\r\nContent-Length: '+str(len(frame)).encode()+b'\r\n\r\n'+frame+b'\r\n')
                self.close_connection=True
            except (ConnectionError,TimeoutError):self.close_connection=True
        def do_POST(self):
            origin=self.headers.get('Origin')
            allowed={f'http://127.0.0.1:{args.port}',f'http://localhost:{args.port}'}
            if origin not in allowed or self.headers.get('X-Mission-Token')!=token:
                return self.send(403,{'error':'Local dashboard origin and token required'})
            if urlsplit(self.path).path!='/api/command':return self.send(404,{'error':'Not found'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=32768:raise ValueError('Invalid request size')
                data=json.loads(self.rfile.read(size))
                if not isinstance(data,dict):raise ValueError('Object required')
                action=data.get('action')
                if not isinstance(action,str) or len(action)>40:raise ValueError('Invalid action')
                payload=data.get('payload',{})
                if not isinstance(payload,dict):raise ValueError('Payload must be an object')
                with lock:
                    if action=='set_view':
                        selected=payload.get('mode')
                        if selected not in ('browser','map','image'):raise ValueError('Unknown view mode')
                        if selected=='image' and args.no_render:raise ValueError('Image rendering is disabled')
                        view[0]=selected;engine.revision+=1
                    else:engine.command(action,payload)
                    result=engine.snapshot()
                # Response transmission is outside the robot-error boundary.
            except (ValueError,TypeError,KeyError,IndexError) as exc:
                return self.send(400,{'error':str(exc)})
            except (ConnectionError,TimeoutError):
                self.close_connection=True
                return
            except Exception as exc:
                with lock:engine.stop();engine.fault=f'{type(exc).__name__}: {exc}'
                return self.send(500,{'error':engine.fault})
            return self.send(200,result)

    http=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    worker=threading.Thread(target=loop,daemon=True)
    worker.start()
    renderer=None
    if args.backend=='native' and not args.no_render:
        renderer=threading.Thread(target=render_loop,daemon=True)
        renderer.start()
    print(f'Mission Companion: http://127.0.0.1:{args.port} ({args.backend})',flush=True)
    print('Simulation only. Camera/microphone remain off until you enable them.',flush=True)
    try:http.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        shutdown.set();http.server_close();worker.join(timeout=5)
        if renderer:renderer.join(timeout=5)
        else:backend.close()


if __name__=='__main__':main()
