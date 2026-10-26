"""Conservative landmark gestures and a closed-vocabulary speech interpreter."""
import math
import re


def gesture(points):
    """Classify 21 MediaPipe landmarks independent of hand scale/translation.

    Only deliberate palm, fist, V-sign and pointing are recognized. Unknown
    hands cause no command. Thumb is excluded to avoid handedness ambiguity.
    """
    if not isinstance(points, list) or len(points) != 21:
        return 'unknown'
    try:
        p=[(float(v['x']),float(v['y']),float(v.get('z',0))) for v in points]
    except (KeyError,TypeError,ValueError):
        return 'unknown'
    if not all(math.isfinite(v) for pt in p for v in pt):
        return 'unknown'
    def dist(a,b):
        return math.dist(p[a],p[b])
    scale=dist(0,9)
    if scale < 0.015:
        return 'unknown'
    # Require the fingertip beyond its PIP knuckle by a palm-relative margin;
    # compare wrist distance rather than image y so rotated hands still work.
    def straight(mcp,pip,tip):
        a=[p[mcp][i]-p[pip][i] for i in range(3)]
        b=[p[tip][i]-p[pip][i] for i in range(3)]
        length=math.sqrt(sum(v*v for v in a)*sum(v*v for v in b))
        return length>1e-8 and sum(x*y for x,y in zip(a,b))/length<-.90
    # A straight finger tilted towards the camera can have a smaller apparent
    # wrist-distance margin. Accept it only with a straight 3D PIP angle too.
    extended=[dist(0,tip)>dist(0,pip)+.32*scale or
              (straight(mcp,pip,tip) and dist(0,tip)>dist(0,pip)+.08*scale)
              for mcp,pip,tip in [(5,6,8),(9,10,12),(13,14,16),(17,18,20)]]
    if all(extended): return 'stop'
    if not any(extended): return 'quiet'
    if extended==[True,True,False,False]: return 'wave'
    if extended==[True,False,False,False]:
        dx=p[8][0]-p[5][0]
        if abs(dx)>scale*0.45:
            return 'left' if dx<0 else 'right'
    return 'unknown'


class GestureGate:
    """Dwell + release latch. Holding a sign never repeats its action."""
    def __init__(self,dwell=0.45):
        self.dwell=dwell
        self.candidate='unknown'
        self.since=0
        self.latched=None
        self.last=-math.inf
        self.unknown_since=None

    def update(self,label,now):
        if not math.isfinite(now) or now<self.last:
            raise ValueError('Gesture time must be monotonic')
        self.last=now
        if label=='unknown':
            if self.unknown_since is None:self.unknown_since=now
            if now-self.unknown_since>=0.2:
                self.latched=None;self.candidate='unknown';self.since=now
            return None
        if self.unknown_since is not None and now-self.unknown_since>=0.2:
            self.latched=None;self.candidate='unknown'
        self.unknown_since=None
        if label!=self.candidate:
            self.candidate,self.since=label,now
        # Stop uses a shorter dwell; still requires multiple camera samples.
        dwell=0.12 if label=='stop' else self.dwell
        if now-self.since>=dwell and self.latched!=label:
            self.latched=label
            return label
        return None


VOICE = {
 'stop':'stop','cancel':'stop','freeze':'stop',
 'hello':'wave','hi':'wave','hey':'wave','hey hi':'wave','wave':'wave','say hello':'wave',
 'bow':'bow','salute':'salute','offer paw':'paw','paw':'paw',
 'celebrate':'celebrate','happy':'celebrate','curious':'curious',
 'quiet':'quiet','be quiet':'quiet',
 'turn left':'left','left':'left','turn right':'right','right':'right',
 'start mission':'mission_start','solve maze':'mission_start',
 'start focus':'focus_start','pause focus':'focus_pause',
 'resume focus':'focus_resume','start game':'game_start',
 'next round':'game_next',
 'wave hello':'wave','wave your hand':'wave','hello jumper':'wave',
 'take a bow':'bow','give me your paw':'paw','do a dance':'celebrate','dance':'celebrate',
 'stop all':'stop','stop everything':'stop',
 'start timer':'focus_start','pause timer':'focus_pause','resume timer':'focus_resume',
 'stop focus':'focus_stop','end focus':'focus_stop','skip break':'focus_skip_break',
}


def parse_voice(text,confidence=1.0):
    if not isinstance(text,str) or len(text)>200:
        return None
    if not isinstance(confidence,(float,int)) or not math.isfinite(confidence):
        return None
    phrase=re.sub(r'[^a-z ]',' ',text.lower())
    phrase=' '.join(phrase.split())
    # No substring matching: "do not stop" must not become a stop command,
    # and descriptions of a mission must never start it.
    phrase=re.sub(r'^(?:hey )?jumper[, ]*','',phrase).strip()
    phrase=re.sub(r'^please\s+','',phrase)
    phrase=re.sub(r'\s+please$','',phrase)
    threshold=0.35 if phrase in ('stop','cancel','freeze') else 0.65
    return VOICE.get(phrase) if confidence>=threshold else None
