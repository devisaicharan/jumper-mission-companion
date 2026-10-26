"""Bounded visitor sessions for the optional hosted simulation service."""
import gzip
import json
import secrets
import threading
import time
from http.cookies import SimpleCookie, CookieError
from urllib.parse import urlsplit
from mission.engine import Engine, KinematicBackend
from mission.navigation import Maze


class HTTPError(Exception):
    def __init__(self,status,message):self.status=status;super().__init__(message)


def origin(value):
    """Accept a complete origin, never a wildcard or a URL with credentials/path."""
    p=urlsplit(value)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.path not in ('','/') or p.query or p.fragment:
        raise ValueError('Expected an exact http(s) origin without a path')
    _=p.port
    return f'{p.scheme}://{p.netloc.lower()}'


def session_cookie(header):
    try:
        c=SimpleCookie();c.load(header or '')
        value=c['mission_session'].value if 'mission_session' in c else ''
        return value if len(value)==43 and all(x.isalnum() or x in '-_' for x in value) else None
    except CookieError:return None


class Session:
    def __init__(self,backend_factory,version,clock=time.monotonic,start=True):
        self.clock=clock;self.created=self.last_seen=clock();self.id=secrets.token_urlsafe(32)
        self.token=secrets.token_urlsafe(32);self.lock=threading.RLock();self.stop_event=threading.Event()
        self.maze=Maze();self.backend=backend_factory(self.maze);self.engine=Engine(self.backend,self.maze)
        self.engine.performance.update(version=version,view_mode='Browser 3D')
        self.view='browser';self.scene=None;self.closed=False
        self.budget=60.;self.budget_at=clock()
        self.worker=threading.Thread(target=self.loop,daemon=True,name='visitor-simulation')
        if start:self.worker.start()

    def snapshot(self):
        with self.lock:
            if self.closed:raise HTTPError(410,'Session ended. Reload to start a new robot.')
            self.last_seen=self.clock();result=self.engine.snapshot();result['render_error']=None
            return result

    def command(self,action,payload):
        with self.lock:
            if self.closed:raise HTTPError(410,'Session ended. Reload to start a new robot.')
            now=self.clock();self.budget=min(60,self.budget+30*(now-self.budget_at));self.budget_at=now
            if self.budget<1:raise HTTPError(429,'Too many commands. Wait a moment and try again.')
            self.budget-=1;self.last_seen=now
            if action=='set_view':
                if payload.get('mode') not in ('browser','map'):raise ValueError('Hosted sessions support Browser 3D or 2D map')
                self.view=payload['mode'];self.engine.revision+=1
                self.engine.performance['view_mode']='Browser 3D' if self.view=='browser' else '2D map'
            else:self.engine.command(action,payload)
            return self.snapshot()

    def scene_bytes(self):
        with self.lock:
            if self.closed:raise HTTPError(410,'Session ended. Reload to reconnect.')
            self.last_seen=self.clock()
            if not hasattr(self.backend,'scene_description'):raise HTTPError(404,'No native scene in preview mode')
            if self.scene is None:
                self.scene=gzip.compress(json.dumps(self.backend.scene_description(),separators=(',',':')).encode(),compresslevel=5)
            return self.scene

    def loop(self):
        last=sample=self.clock();sample_sim=self.backend.state()['sim_time']
        while not self.stop_event.is_set():
            began=self.clock();elapsed=began-last;last=began;dt=min(.02,max(.005,elapsed))
            try:
                with self.lock:
                    self.engine.now+=max(0,elapsed-dt)
                    if elapsed>2:self.engine.quiet_background()
                    self.engine.tick(dt)
                    self.engine.performance['control_step_ms']=round((self.clock()-began)*1000,1)
                    if began-sample>=1:
                        sim=self.backend.state()['sim_time']
                        self.engine.performance['real_time_factor']=round(max(0,sim-sample_sim)/(began-sample),2)
                        sample=began;sample_sim=sim
            except Exception as exc:
                with self.lock:
                    self.engine.stop();self.engine.fault=f'Simulation stopped: {type(exc).__name__}. Reset or release this session.'
                self.stop_event.set()
            self.stop_event.wait(max(.001,.02-(self.clock()-began)))

    def close(self):
        with self.lock:
            if self.closed:return
            self.closed=True;self.stop_event.set();self.engine.stop()
        if self.worker.is_alive():self.worker.join(timeout=5)
        with self.lock:self.backend.close()


class SessionPool:
    def __init__(self,factory,version,limit=1,idle=300,lifetime=7200,clock=time.monotonic,start=True):
        self.factory=factory;self.version=version;self.limit=limit;self.idle=idle;self.lifetime=lifetime
        self.clock=clock;self.start=start;self.sessions={};self.lock=threading.RLock()

    def expire(self):
        with self.lock:
            now=self.clock()
            for sid,s in list(self.sessions.items()):
                with s.lock:
                    expired=now-s.created>=self.lifetime or (now-s.last_seen>=self.idle and s.engine.activity!='focus')
                if expired:self.sessions.pop(sid);s.close()

    def get(self,sid):
        self.expire()
        with self.lock:
            s=self.sessions.get(sid)
            if not s:raise HTTPError(401,'Session expired or not started. Reload the page to reconnect.')
            return s

    def acquire(self,sid):
        self.expire()
        with self.lock:
            if sid in self.sessions:return self.sessions[sid],False
            if len(self.sessions)>=self.limit:raise HTTPError(503,'The hosted robot is in use. Try again after that visitor releases it, or run the Windows version.')
            try:s=Session(self.factory,self.version,self.clock,self.start)
            except Exception as exc:
                print(f'Native session startup failed: {type(exc).__name__}: {exc}',flush=True)
                raise HTTPError(503,'The simulation could not start on this host. Check deployment logs and available memory.') from exc
            self.sessions[s.id]=s;return s,True

    def release(self,sid):
        with self.lock:
            s=self.sessions.pop(sid,None)
            if s:s.close()

    def close(self):
        with self.lock:
            for sid in list(self.sessions):self.release(sid)
