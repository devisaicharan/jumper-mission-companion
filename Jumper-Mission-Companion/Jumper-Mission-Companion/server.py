"""Run the local Mission Companion dashboard. No publishing or cloud account."""
import argparse
import io
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


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--backend',choices=['native','preview'],default='native')
    parser.add_argument('--upstream',default=str(ROOT.parent/'jumper-upstream'))
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--no-render',action='store_true')
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
    lock=threading.RLock()
    shutdown=threading.Event()
    token=secrets.token_urlsafe(24)
    picture=[None]
    render_fault=[None]

    def loop():
        last=time.monotonic()
        while not shutdown.is_set():
            began=time.monotonic();elapsed=began-last;last=began
            dt=min(0.25,max(0.001,elapsed))
            try:
                with lock:
                    engine.now+=max(0,elapsed-dt)
                    if elapsed>2:
                        # Resume from laptop sleep/long stalls without replaying
                        # stale motion requests or silently losing timer minutes.
                        engine.stop()
                        engine._event('watchdog','Control loop paused; activities cancelled')
                    engine.tick(dt)
            except Exception as exc:
                with lock:
                    engine.stop();engine.fault=f'{type(exc).__name__}: {exc}'
                    engine._event('fault',engine.fault)
                    print(f'Simulation error: {engine.fault}',flush=True)
                # Renderer failures are surfaced, never substituted by a fake image.
                render_fault[0]=str(exc)
                shutdown.set()
            shutdown.wait(max(0,0.02-(time.monotonic()-began)))

    def render_loop():
        # One owner for the GL context. Only scene preparation shares the physics
        # lock; slow GPU readback and JPEG compression never hold up commands.
        from PIL import Image
        try:
            while not shutdown.is_set():
                began=time.monotonic()
                with lock: backend.prepare_render()
                pixels=backend.finish_render()
                out=io.BytesIO()
                Image.fromarray(pixels).save(out,format='JPEG',quality=76)
                picture[0]=out.getvalue()
                shutdown.wait(max(0,.1-(time.monotonic()-began)))
        except Exception as exc:
            render_fault[0]=f'{type(exc).__name__}: {exc}'
            print(f'Render error (controls remain available): {render_fault[0]}',flush=True)
        finally:backend.close()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_args): pass
        def send(self,status,body,kind='application/json'):
            if isinstance(body,(dict,list)):body=json.dumps(body,allow_nan=False).encode()
            if isinstance(body,str):body=body.encode()
            self.send_response(status)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.end_headers()
            try:self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):pass
        def do_GET(self):
            path=urlsplit(self.path).path
            if path=='/api/state':
                with lock:
                    result=engine.snapshot();result['render_error']=render_fault[0]
                return self.send(200,result)
            if path=='/api/config':return self.send(200,{'token':token,'backend':args.backend})
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
                    engine.command(action,payload)
                    result=engine.snapshot()
                return self.send(200,result)
            except (ValueError,TypeError,KeyError,IndexError) as exc:
                return self.send(400,{'error':str(exc)})
            except Exception as exc:
                with lock:engine.stop();engine.fault=f'{type(exc).__name__}: {exc}'
                return self.send(500,{'error':engine.fault})

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
