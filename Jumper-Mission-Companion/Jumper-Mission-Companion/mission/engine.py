"""One owner for all six features, with stop priority and bounded commands."""
from collections import deque
import math
from .activities import Focus, MemoryGame, Expressions
from .navigation import Maze, Navigator
from .perception import GestureGate, gesture, parse_voice


class KinematicBackend:
    """Explicit test/preview backend. Never presented as robot physics."""
    def __init__(self): self.reset()
    def reset(self):
        self.x=self.y=self.yaw=self.time=0.;self.mode='locomotion'
        self.control=(0.,0.,0.);self.end=0
    def stop(self): self.control=(0.,0.,0.);self.mode='locomotion'
    def motion(self,name): self.control=(0.,0.,0.);self.mode=name;self.end=self.time+1.2
    def step(self,seconds=0.02):
        self.time+=seconds
        if self.mode!='locomotion' and self.time>=self.end: self.mode='locomotion'
        if self.mode=='locomotion':
            vx,vy,wz=self.control
            c,s=math.cos(self.yaw),math.sin(self.yaw)
            self.x+=(c*vx-s*vy)*0.25*seconds
            self.y+=(s*vx+c*vy)*0.25*seconds
            self.yaw+=wz*seconds
    def state(self):
        return dict(x=self.x,y=self.y,z=0.107,yaw=self.yaw,tilt=0.,mode=self.mode,
                    running=True,sim_time=self.time,backend='kinematic-preview',max_torque=0.)
    def close(self): pass


class Engine:
    def __init__(self,backend,maze=None,seed=None):
        self.backend=backend;self.maze=maze or Maze()
        self.nav=Navigator(self.maze);self.focus=Focus();self.game=MemoryGame(seed)
        self.expressions=Expressions();self.gate=GestureGate()
        self.activity='manual';self.now=0.;self.logs=deque(maxlen=120)
        self.command_id=0;self.manual_until=0.;self.fault=None
        self.revision=0
        self.heartbeat=0.;self.camera_enabled=False
        self.last_hand=0.;self.camera_motion=False
        self._event('ready','Controller ready')

    def _event(self,kind,message):
        self.logs.append(dict(at=round(self.now,3),kind=kind,message=message))

    def _manual(self):
        self.nav.cancel();self.focus.command('stop',self.now);self.game.stop()
        self.expressions.cancel(self.backend,self.now)
        self.activity='manual'

    def stop(self):
        self._manual();self.manual_until=0.;self.camera_motion=False
        self._event('stop','All activities cancelled; explicit restart required')

    def command(self,action,payload=None,source='button'):
        payload=payload or {}
        self.command_id+=1
        self.revision+=1
        if action=='heartbeat':
            self.heartbeat=self.now;return
        if action=='stop': self.stop();return
        if action=='reset':
            self.stop();self.maze.reset();self.backend.reset();self.fault=None
            self._event('reset','Simulation reset');return
        if self.fault: raise ValueError('Reset the simulation after its fault')
        if action=='configure_focus':
            self.focus.configure(payload.get('focus'),payload.get('rest'));return
        if action=='voice':
            parsed=parse_voice(payload.get('text'),payload.get('confidence',1))
            self._event('voice',f"{payload.get('text','')[:100]} → {parsed or 'no match'}")
            if parsed: return self.command(parsed,source='voice')
            return
        if action=='camera_enable':
            self.camera_enabled=bool(payload.get('enabled'));self.gate=GestureGate()
            self.last_hand=self.now
            if not self.camera_enabled and self.camera_motion: self.stop()
            return
        if action=='landmarks':
            if not self.camera_enabled: return
            label=gesture(payload.get('points'))
            if label!='unknown': self.last_hand=self.now
            triggered=self.gate.update(label,self.now)
            if triggered:
                self._event('gesture',triggered)
                self.command(triggered,source='gesture')
            return
        if action in ('wave','bow','paw','salute') and self.game.state=='answering':
            correct=self.game.answer(action)
            self._event('game','Correct' if correct else 'Wrong answer — restart when ready')
            if self.game.state=='won':
                self.expressions.enqueue(['salute'],'success')
            elif self.game.state=='lost':
                self.expressions.enqueue(['bow'],'disappointed')
            return
        if action in ('wave','bow','paw','salute','celebrate','curious'):
            self._manual()
            self.expressions.enqueue([action],{'curious':'curiosity','celebrate':'joy'}.get(action,action))
        elif action in ('left','right'):
            self._manual();self.backend.control=(0.,0.,0.5 if action=='left' else -0.5)
            self.manual_until=self.now+0.6
            self.camera_motion=source=='gesture'
        elif action=='quiet':
            self.expressions.cancel(self.backend,self.now)
            if self.activity=='game':self.game.stop();self.activity='manual'
            self._event('quiet','Optional motions cancelled')
        elif action=='mission_start':
            self._manual();self.activity='mission'
            status=self.nav.start(self.backend.state(),self.now)
            self._event('mission',status)
        elif action=='toggle_obstacle':
            x,y=payload.get('x'),payload.get('y')
            if not isinstance(x,int) or not isinstance(y,int): raise ValueError('Integer cell required')
            if not (0<x<self.maze.w-1 and 0<y<self.maze.h-1):
                raise ValueError('Boundary walls are fixed')
            pose=self.backend.state();cell=(x,y)
            if cell in (self.maze.locate(pose['x'],pose['y']),self.maze.goal):
                raise ValueError('Cannot block the robot or goal')
            adding=cell not in self.maze.blocked
            if adding:
                self.maze.blocked.add(cell)
                if not self.maze.clear(pose['x'],pose['y']):
                    self.maze.blocked.remove(cell)
                    raise ValueError('New obstacle would intersect the robot envelope')
            else:self.maze.blocked.remove(cell)
            if hasattr(self.backend,'set_obstacle'):
                try:self.backend.set_obstacle(cell,adding)
                except Exception:
                    if adding:self.maze.blocked.remove(cell)
                    else:self.maze.blocked.add(cell)
                    raise
            if self.nav.status=='running':self.nav.replan(pose,self.now)
            self._event('map',f'Obstacle {"added" if adding else "removed"} at {x}, {y}')
        elif action.startswith('focus_'):
            cmd=action.split('_',1)[1]
            if cmd=='start':
                self._manual();self.activity='focus'
            event=self.focus.command(cmd,self.now)
            if event=='quiet':self.expressions.cancel(self.backend,self.now)
            elif event:self.expressions.enqueue([event],'focus')
        elif action=='game_start':
            self._manual();self.activity='game'
            self.expressions.enqueue(self.game.start(),'watch the sequence')
        elif action=='game_next':
            if self.activity!='game':raise ValueError('Start a game first')
            if self.expressions.active or self.expressions.queue:
                raise ValueError('Wait for the current motion to finish')
            self.expressions.enqueue(self.game.next_round(),'watch the sequence')
        else:
            raise ValueError('Unknown command')
        self._event(source,action)

    def tick(self,dt=0.02):
        if not math.isfinite(dt) or not 0<dt<=0.25: raise ValueError('Invalid control timestep')
        self.now+=dt
        self.revision+=1
        pose=self.backend.state()
        if pose['tilt']>0.8 or not all(math.isfinite(pose[k]) for k in ('x','y','z','yaw')):
            if not self.fault:
                self.stop();self.fault='Robot tilt/state limit reached';self._event('fault',self.fault)
        if self.now-self.heartbeat>2 and (self.activity!='manual' or
                self.expressions.active or self.expressions.queue or self.manual_until):
            self.stop();self._event('watchdog','UI disconnected; actions cancelled')
        if self.camera_motion and self.now-self.last_hand>0.6:
            self.backend.control=(0.,0.,0.);self.camera_motion=False
        if self.manual_until and self.now>=self.manual_until:
            self.backend.control=(0.,0.,0.);self.manual_until=0.
        if not self.fault:
            if self.activity=='mission':
                before=self.nav.status
                self.backend.control=self.nav.tick(pose,self.now)
                if self.nav.status!=before:
                    self._event('mission',self.nav.status)
                    if self.nav.status=='complete':self.expressions.enqueue(['salute'],'mission complete')
            if self.activity=='focus':
                event=self.focus.tick(self.now)
                if event:self.expressions.enqueue([event],'focus completed')
            event=self.expressions.tick(self.backend,self.now)
            if event:
                kind,symbol=event;self._event('motion',f'{kind}: {symbol}')
                if kind=='started' and self.game.state=='showing':self.game.cue=symbol
                if kind=='fault':self.fault=symbol;self.game.stop();self.nav.cancel()
            if self.game.state=='showing' and not self.expressions.active and not self.expressions.queue:
                self.game.ready();self._event('game','Your turn')
        self.backend.step(dt)

    def snapshot(self):
        return dict(revision=self.revision,time=round(self.now,3),activity=self.activity,fault=self.fault,
            robot=self.backend.state(),focus=self.focus.snapshot(self.now),game=self.game.snapshot(),
            expression=dict(label=self.expressions.label,active=self.expressions.active,
                queued=len(self.expressions.queue),fault=self.expressions.fault),
            navigation=dict(status=self.nav.status,path=self.nav.path,replans=self.nav.replans),
            maze=dict(rows=self.maze.rows,blocked=sorted(self.maze.blocked),
                width=self.maze.w,height=self.maze.h,cell=self.maze.cell,goal=self.maze.goal),
            camera_enabled=self.camera_enabled,logs=list(self.logs))
