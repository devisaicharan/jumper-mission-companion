"""Hosted WSGI application; local server.py and Windows startup stay separate."""
import atexit
import json
import mimetypes
import os
from pathlib import Path
import secrets
import threading
from urllib.parse import unquote
from mission.hosting import HTTPError,SessionPool,origin,session_cookie
from mission.engine import KinematicBackend
from server import VERSION

ROOT=Path(__file__).resolve().parent


class HostedApp:
    def __init__(self,backend='native',upstream=None,origins=(),limit=1,idle=300,lifetime=7200,secure=True,factory=None,start=True):
        self.backend=backend;self.origins={origin(v) for v in origins};self.secure=secure
        if not self.origins:raise ValueError('Set PUBLIC_ORIGIN or RENDER_EXTERNAL_URL before starting hosted mode')
        if secure and any(not v.startswith('https://') for v in self.origins):raise ValueError('Public hosted origins must use HTTPS')
        if factory is None:
            if backend=='preview':factory=lambda maze:KinematicBackend()
            elif backend=='native':
                def factory(maze):
                    from mission.native import NativeJumper
                    return NativeJumper(upstream or ROOT.parent/'jumper-upstream',maze.obstacles(mutable=True))
            else:raise ValueError('Unknown hosted backend')
        self.pool=SessionPool(factory,VERSION,limit,idle,lifetime,start=start)
        self.closed=threading.Event();self.janitor=threading.Thread(target=self.sweep,daemon=True)
        if start:self.janitor.start()

    def sweep(self):
        while not self.closed.wait(15):self.pool.expire()

    def close(self):self.closed.set();self.pool.close()

    def __call__(self,environ,start_response):
        headers=[('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('Referrer-Policy','no-referrer'),
                 ('X-Frame-Options','DENY'),('Permissions-Policy','camera=(self), microphone=(self)')]
        try:status,body,kind,extra=self.route(environ);headers+=extra
        except HTTPError as exc:status,body,kind=exc.status,{'error':str(exc)},'application/json'
        except (ValueError,TypeError,KeyError,IndexError):status,body,kind=400,{'error':'Invalid command or configuration value'},'application/json'
        except Exception as exc:
            print(f'Hosted request failed: {type(exc).__name__}: {exc}',flush=True)
            status,body,kind=500,{'error':'The hosted request failed. Try reconnecting.'},'application/json'
        if isinstance(body,(dict,list)):body=json.dumps(body,allow_nan=False).encode()
        elif isinstance(body,str):body=body.encode()
        headers.extend([('Content-Type',kind),('Content-Length',str(len(body)))])
        labels={200:'OK',400:'Bad Request',401:'Unauthorized',403:'Forbidden',404:'Not Found',405:'Method Not Allowed',410:'Gone',413:'Content Too Large',429:'Too Many Requests',500:'Internal Server Error',503:'Service Unavailable'}
        start_response(f'{status} {labels.get(status,"Error")}',headers)
        return [body]

    def route(self,e):
        method=e['REQUEST_METHOD'];path=e.get('PATH_INFO','/');sid=session_cookie(e.get('HTTP_COOKIE'))
        if method=='GET' and path=='/healthz':return 200,{'ok':True,'version':VERSION,'backend':self.backend},'application/json',[]
        if method=='GET' and path=='/api/config':
            # Navigation/config starts a session, but a cross-site fetch cannot.
            if e.get('HTTP_SEC_FETCH_SITE')=='cross-site':raise HTTPError(403,'Open the dashboard directly to start a session')
            s,new=self.pool.acquire(sid)
            cookie=f'mission_session={s.id}; Path=/; HttpOnly; SameSite=Lax'+('; Secure' if self.secure else '')
            return 200,dict(token=s.token,backend=self.backend,version=VERSION,view=s.view,image_available=False,hosted=True,session_lifetime_seconds=self.pool.lifetime,poll_interval_ms=150), 'application/json',[('Set-Cookie',cookie)]
        if path.startswith('/api/'):
            s=self.pool.get(sid)
            if method=='GET':
                if path=='/api/state':return 200,s.snapshot(),'application/json',[]
                if path=='/api/scene':return 200,s.scene_bytes(),'application/json',[('Content-Encoding','gzip')]
                raise HTTPError(404,'Hosted image rendering is disabled; use Browser 3D or 2D map')
            if method!='POST':raise HTTPError(405,'Method not allowed')
            if e.get('HTTP_ORIGIN') not in self.origins or not secrets.compare_digest(e.get('HTTP_X_MISSION_TOKEN',''),s.token):raise HTTPError(403,'Dashboard origin and session token required')
            if path=='/api/session/end':
                self.pool.release(s.id)
                return 200,{'ended':True},'application/json',[('Set-Cookie','mission_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax'+('; Secure' if self.secure else ''))]
            if path!='/api/command':raise HTTPError(404,'Not found')
            try:size=int(e.get('CONTENT_LENGTH') or '0')
            except ValueError:raise HTTPError(400,'Invalid content length')
            if not 0<size<=32768:raise HTTPError(413,'Command body must be between 1 and 32768 bytes')
            if e.get('CONTENT_TYPE','').split(';')[0]!='application/json':raise HTTPError(400,'JSON content type required')
            data=json.loads(e['wsgi.input'].read(size))
            if not isinstance(data,dict):raise HTTPError(400,'Object required')
            action=data.get('action');payload=data.get('payload',{})
            if not isinstance(action,str) or len(action)>40 or not isinstance(payload,dict):raise HTTPError(400,'Invalid command')
            try:result=s.command(action,payload)
            except (ValueError,TypeError,KeyError,IndexError) as exc:raise HTTPError(400,str(exc)) from exc
            return 200,result,'application/json',[]
        if method!='GET':raise HTTPError(405,'Method not allowed')
        file=(ROOT/'static'/('index.html' if path=='/' else unquote(path).lstrip('/'))).resolve()
        if not file.is_relative_to(ROOT/'static') or not file.is_file() or file.name.startswith('.') or file.name=='_redirects':raise HTTPError(404,'Not found')
        kind={'.js':'text/javascript','.mjs':'text/javascript','.wasm':'application/wasm','.task':'application/octet-stream'}.get(file.suffix) or mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
        return 200,file.read_bytes(),kind,[]


def create_app():
    origins=[v.strip() for v in os.environ.get('ALLOWED_ORIGINS','').split(',') if v.strip()]
    primary=os.environ.get('PUBLIC_ORIGIN') or os.environ.get('RENDER_EXTERNAL_URL')
    if primary:origins.append(primary)
    local=os.environ.get('HOSTED_LOCAL_TEST')=='1'
    def number(name,default,low,high):
        value=int(os.environ.get(name,str(default)))
        if not low<=value<=high:raise ValueError(f'{name} must be between {low} and {high}')
        return value
    app=HostedApp(backend=os.environ.get('MISSION_BACKEND','native'),upstream=os.environ.get('UPSTREAM_DIR'),origins=origins,
        limit=number('MAX_SESSIONS',1,1,8),idle=number('SESSION_IDLE_SECONDS',300,30,3600),
        lifetime=number('SESSION_MAX_SECONDS',7200,60,14400),secure=not local)
    atexit.register(app.close);return app
