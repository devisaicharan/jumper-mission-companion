"""Focus sessions, memory game and acknowledged expression sequencing."""
import math
import random


class Focus:
    def __init__(self):
        self.state='idle';self.deadline=None;self.remaining=None
        self.duration=1500.;self.rest=300.;self.sessions=0

    def configure(self,focus,rest):
        if self.state!='idle': raise ValueError('Stop focus before changing durations')
        if not all(isinstance(v,(int,float)) and math.isfinite(v) and 1<=v<=14400
                   for v in (focus,rest)):
            raise ValueError('Durations must be between 1 and 14400 seconds')
        self.duration,self.rest=float(focus),float(rest)

    def command(self,cmd,now):
        if cmd=='start' and self.state=='idle':
            self.state='focus';self.deadline=now+self.duration;return 'wave'
        if cmd=='pause' and self.state=='focus':
            self.remaining=max(0,self.deadline-now);self.deadline=None
            self.state='paused';return 'quiet'
        if cmd=='resume' and self.state=='paused':
            self.deadline=now+self.remaining;self.remaining=None
            self.state='focus';return 'quiet'
        if cmd=='stop':
            self.state='idle';self.deadline=None;self.remaining=None;return 'quiet'
        raise ValueError(f'Cannot {cmd} focus in {self.state}')

    def tick(self,now):
        if self.deadline is None or now<self.deadline: return None
        if self.state=='focus':
            self.sessions+=1;self.state='break';self.deadline=now+self.rest
            return 'celebrate'
        self.state='idle';self.deadline=None;return 'bow'

    def snapshot(self,now):
        return dict(state=self.state,remaining=max(0,self.deadline-now)
            if self.deadline is not None else self.remaining,
            focus_seconds=self.duration,break_seconds=self.rest,sessions=self.sessions)


class MemoryGame:
    symbols=('wave','bow','paw','salute')
    def __init__(self,seed=None):
        self.rng=random.Random(seed);self.sequence=[];self.state='idle'
        self.index=0;self.score=0;self.best=0;self.cue=None

    def start(self):
        self.sequence=[];self.score=0;self.state='idle'
        return self.next_round()

    def next_round(self):
        if self.state not in ('idle','won','lost'):
            raise ValueError('Finish or stop the current round first')
        if self.state=='lost':
            raise ValueError('Start a new game after a wrong answer')
        if len(self.sequence)>=20:
            self.state='complete';return []
        self.sequence.append(self.rng.choice(self.symbols));self.index=0
        self.state='showing';self.cue=None
        return list(self.sequence)

    def ready(self):
        if self.state=='showing': self.state='answering';self.cue=None

    def answer(self,symbol):
        if self.state!='answering': raise ValueError('Wait until the sequence finishes')
        if symbol not in self.symbols: raise ValueError('Unknown game symbol')
        if symbol!=self.sequence[self.index]:
            self.state='lost';return False
        self.index+=1
        if self.index==len(self.sequence):
            self.state='won';self.score=len(self.sequence);self.best=max(self.best,self.score)
        return True

    def stop(self):
        self.state='idle';self.sequence=[];self.index=0;self.cue=None

    def snapshot(self):
        # Do not expose the secret sequence during the answering phase.
        return dict(state=self.state,level=len(self.sequence),answered=self.index,
                    score=self.score,best=self.best,cue=self.cue)


class Expressions:
    """A bounded queue: one acknowledged motion at a time, timeout on stalls."""
    def __init__(self):
        self.queue=[];self.active=None;self.started=0;self.entered=False
        self.label='calm';self.fault=None;self.not_before=0
        self.excerpt_cancelled=False

    def enqueue(self,symbols,label):
        if len(self.queue)+len(symbols)>24: raise ValueError('Motion queue is full')
        if any(s not in ('wave','bow','paw','salute','celebrate','curious') for s in symbols):
            raise ValueError('Unsupported motion')
        self.queue.extend(symbols);self.label=label

    def cancel(self,backend,now=0):
        self.queue=[];self.active=None;self.entered=False;self.label='calm'
        self.fault=None;self.not_before=now+0.1
        self.excerpt_cancelled=False
        backend.stop()

    def tick(self,backend,now):
        state=backend.state()
        if self.active is not None:
            if state['mode']!='locomotion': self.entered=True
            # The upstream dance is nearly four minutes. A focus reward is
            # deliberately a five-second excerpt, exited by the controller's
            # supported leave binding, never by overriding joint targets.
            if self.active=='celebrate' and self.entered and now-self.started>=5 and not self.excerpt_cancelled:
                backend.stop();self.excerpt_cancelled=True
            if self.entered and state['mode']=='locomotion' and now-self.started>0.2:
                done=self.active;self.active=None;self.not_before=now+0.4
                return ('done',done)
            if now-self.started>35:
                self.fault='Motion did not complete within 35 seconds'
                backend.stop();self.queue=[];self.active=None
                return ('fault',self.fault)
        elif self.queue and now>=self.not_before and state['mode']=='locomotion' and state['running']:
            self.active=self.queue.pop(0);self.started=now;self.entered=False
            self.excerpt_cancelled=False
            backend.motion(self.active)
            return ('started',self.active)
        return None
