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
    extended=[dist(0,tip)>dist(0,pip)+0.32*scale
              for tip,pip in [(8,6),(12,10),(16,14),(20,18)]]
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

    def update(self,label,now):
        if not math.isfinite(now) or now<self.last:
            raise ValueError('Gesture time must be monotonic')
        self.last=now
        if label!=self.candidate:
            self.candidate,self.since=label,now
        if label=='unknown':
            if now-self.since>=0.2: self.latched=None
            return None
        # Stop uses a shorter dwell; still requires multiple camera samples.
        dwell=0.12 if label=='stop' else self.dwell
        if now-self.since>=dwell and self.latched!=label:
            self.latched=label
            return label
        return None


VOICE = {
 'stop':'stop','cancel':'stop','freeze':'stop',
 'hello':'wave','wave':'wave','say hello':'wave',
 'bow':'bow','salute':'salute','offer paw':'paw','paw':'paw',
 'celebrate':'celebrate','happy':'celebrate','curious':'curious',
 'quiet':'quiet','be quiet':'quiet',
 'turn left':'left','left':'left','turn right':'right','right':'right',
 'start mission':'mission_start','solve maze':'mission_start',
 'start focus':'focus_start','pause focus':'focus_pause',
 'resume focus':'focus_resume','start game':'game_start',
 'next round':'game_next',
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
    threshold=0.35 if phrase in ('stop','cancel','freeze') else 0.65
    return VOICE.get(phrase) if confidence>=threshold else None
