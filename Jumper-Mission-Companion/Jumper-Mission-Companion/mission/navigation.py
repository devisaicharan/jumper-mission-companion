"""Footprint-aware A*, dynamic occupancy and a measured-pose follower."""
import heapq
import math


class Maze:
    def __init__(self, rows=None, cell=0.6):
        self.rows=rows or [
            '#########',
            '#.......#',
            '#..#....#',
            '#..#.#..#',
            '#....#..#',
            '#.##....#',
            '#.......#',
            '#########',
        ]
        if not self.rows or len({len(r) for r in self.rows})!=1:
            raise ValueError('Maze must be rectangular')
        if not math.isfinite(cell) or cell<0.5:
            raise ValueError('Cells must be at least 0.5m for this footprint')
        if any(c not in '.#' for r in self.rows for c in r):
            raise ValueError('Only . and # are valid cells')
        self.h,self.w=len(self.rows),len(self.rows[0])
        self.cell=cell
        self.blocked={(x,y) for y,r in enumerate(self.rows) for x,c in enumerate(r) if c=='#'}
        self.radius=0.24 # conservative horizontal envelope for nominal stance
        self.offset=(1,1)
        self.goal=(self.w-2,self.h-2)

    def world(self,cell):
        return ((cell[0]-self.offset[0])*self.cell,
                (self.offset[1]-cell[1])*self.cell)

    def reset(self):
        self.blocked={(x,y) for y,row in enumerate(self.rows) for x,c in enumerate(row) if c=='#'}

    def locate(self,x,y):
        return (round(x/self.cell+self.offset[0]),round(self.offset[1]-y/self.cell))

    def clear(self,x,y):
        # Disc vs each occupied cell's AABB, including the robot envelope.
        for bx,by in self.blocked:
            wx,wy=self.world((bx,by))
            dx=max(abs(x-wx)-self.cell/2,0)
            dy=max(abs(y-wy)-self.cell/2,0)
            if dx*dx+dy*dy < self.radius**2:
                return False
        return -0.5*self.cell<=x<self.w*self.cell and -self.h*self.cell<y<=self.cell/2

    def traversable(self,c):
        return (0<=c[0]<self.w and 0<=c[1]<self.h and c not in self.blocked
                and self.clear(*self.world(c)))

    def segment_clear(self,a,b):
        distance=math.dist(a,b)
        n=max(1,math.ceil(distance/0.03))
        return all(self.clear(a[0]+(b[0]-a[0])*i/n,
                              a[1]+(b[1]-a[1])*i/n) for i in range(n+1))

    def plan(self,start,goal=None):
        start,goal=tuple(start),tuple(goal or self.goal)
        if not self.traversable(start) or not self.traversable(goal):
            return []
        queue=[(0,0,start)]
        previous={start:None}
        cost={start:0}
        serial=0
        while queue:
            _,_,node=heapq.heappop(queue)
            if node==goal:
                route=[]
                while node is not None:
                    route.append(node);node=previous[node]
                return route[::-1]
            for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                nxt=node[0]+dx,node[1]+dy
                nc=cost[node]+1
                if self.traversable(nxt) and nc<cost.get(nxt,math.inf):
                    if not self.segment_clear(self.world(node),self.world(nxt)): continue
                    cost[nxt]=nc;previous[nxt]=node;serial+=1
                    h=abs(nxt[0]-goal[0])+abs(nxt[1]-goal[1])
                    heapq.heappush(queue,(nc+h,serial,nxt))
        return []

    def obstacles(self,mutable=False):
        if mutable:
            return [(*self.world((x,y)),self.cell/2,self.cell/2,(x,y) in self.blocked,x,y)
                    for y in range(self.h) for x in range(self.w)]
        return [(*self.world(c),self.cell/2,self.cell/2) for c in sorted(self.blocked)]


class Navigator:
    def __init__(self,maze):
        self.maze=maze
        self.path=[]
        self.status='idle'
        self.best=math.inf
        self.progress_at=0
        self.replans=0

    def start(self,pose,now):
        start=self.maze.locate(pose['x'],pose['y'])
        self.path=self.maze.plan(start)
        self.status='running' if self.path else 'blocked'
        self.progress_at=now
        self.best=math.inf
        return self.status

    def cancel(self):
        self.path=[];self.status='idle'

    def replan(self,pose,now):
        self.replans+=1
        return self.start(pose,now)

    def tick(self,pose,now):
        if self.status!='running': return (0.,0.,0.)
        current=(pose['x'],pose['y'])
        if not self.maze.clear(*current):
            self.status='clearance_fault';return (0.,0.,0.)
        while self.path and math.dist(current,self.maze.world(self.path[0]))<0.09:
            self.path.pop(0);self.best=math.inf;self.progress_at=now
        if not self.path:
            self.status='complete';return (0.,0.,0.)
        target=self.maze.world(self.path[0])
        if not self.maze.segment_clear(current,target):
            self.replan(pose,now)
            return (0.,0.,0.)
        distance=math.dist(current,target)
        if distance<self.best-0.015:
            self.best=distance;self.progress_at=now
        if now-self.progress_at>12:
            self.status='stalled';return (0.,0.,0.)
        # Hexapod can strafe: world-vector rotated into measured body frame.
        # No yaw command needed at cell corners, avoiding a spinning footprint.
        dx,dy=target[0]-current[0],target[1]-current[1]
        c,s=math.cos(pose['yaw']),math.sin(pose['yaw'])
        vx=c*dx+s*dy;vy=-s*dx+c*dy
        norm=max(distance,1e-6)
        speed=min(0.55,distance*1.8)
        return (speed*vx/norm,speed*vy/norm,0.)
