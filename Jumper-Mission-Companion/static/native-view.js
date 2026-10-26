// Local WebGL display of the official mesh geometry and measured MuJoCo poses.
// This renderer never simulates, chooses commands, or invents joint motion.
const clamp=x=>Math.max(0,Math.min(1,x));
const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const norm=a=>{const n=Math.hypot(...a)||1;return a.map(x=>x/n);};
function multiply(a,b){const c=new Float32Array(16);for(let j=0;j<4;j++)for(let i=0;i<4;i++)for(let k=0;k<4;k++)c[j*4+i]+=a[k*4+i]*b[j*4+k];return c;}
function viewMatrix(eye,target){const f=norm(target.map((v,i)=>v-eye[i])),s=norm(cross(f,[0,0,1])),u=cross(s,f);return new Float32Array([s[0],u[0],-f[0],0,s[1],u[1],-f[1],0,s[2],u[2],-f[2],0,-dot(s,eye),-dot(u,eye),dot(f,eye),1]);}
function perspective(aspect){const f=1/Math.tan(Math.PI/7),near=.015,far=80;return new Float32Array([f/aspect,0,0,0,0,f,0,0,0,0,(far+near)/(near-far),-1,0,0,2*far*near/(near-far),0]);}
function quat(m){
 let x,y,z,w,t=m[0]+m[4]+m[8];
 if(t>0){const s=Math.sqrt(t+1)*2;w=s/4;x=(m[7]-m[5])/s;y=(m[2]-m[6])/s;z=(m[3]-m[1])/s;}
 else if(m[0]>m[4]&&m[0]>m[8]){const s=Math.sqrt(1+m[0]-m[4]-m[8])*2;w=(m[7]-m[5])/s;x=s/4;y=(m[1]+m[3])/s;z=(m[2]+m[6])/s;}
 else if(m[4]>m[8]){const s=Math.sqrt(1+m[4]-m[0]-m[8])*2;w=(m[2]-m[6])/s;x=(m[1]+m[3])/s;y=s/4;z=(m[5]+m[7])/s;}
 else{const s=Math.sqrt(1+m[8]-m[0]-m[4])*2;w=(m[3]-m[1])/s;x=(m[2]+m[6])/s;y=(m[5]+m[7])/s;z=s/4;}
 return norm([x,y,z,w]);
}
function transform(p,q,scale=[1,1,1]){const [x,y,z,w]=q;return new Float32Array([
 (1-2*y*y-2*z*z)*scale[0],(2*x*y+2*z*w)*scale[0],(2*x*z-2*y*w)*scale[0],0,
 (2*x*y-2*z*w)*scale[1],(1-2*x*x-2*z*z)*scale[1],(2*y*z+2*x*w)*scale[1],0,
 (2*x*z+2*y*w)*scale[2],(2*y*z-2*x*w)*scale[2],(1-2*x*x-2*y*y)*scale[2],0,...p,1]);}
function binary(encoded,Type){const raw=atob(encoded),bytes=new Uint8Array(raw.length);for(let i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);return new Type(bytes.buffer);}

export class NativeView {
 constructor(canvas,description){
  this.canvas=canvas;const gl=canvas.getContext('webgl2',{antialias:false,alpha:false,powerPreference:'low-power'});
  if(!gl)throw Error('3D graphics unavailable. Use the live 2D view.');this.gl=gl;
  const shader=(type,source)=>{const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;};
  const program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,`#version 300 es
   in vec3 aPosition;uniform mat4 uModel,uVP;out vec3 vWorld;
   void main(){vWorld=(uModel*vec4(aPosition,1.)).xyz;gl_Position=uVP*vec4(vWorld,1.);}`));
  gl.attachShader(program,shader(gl.FRAGMENT_SHADER,`#version 300 es
   precision highp float;in vec3 vWorld;uniform vec4 uColor;uniform float uChecker;out vec4 color;
   void main(){vec3 n=normalize(cross(dFdx(vWorld),dFdy(vWorld)));if(!gl_FrontFacing)n=-n;
    float light=.60+.40*max(0.,dot(n,normalize(vec3(-.4,-.6,1.))));
    float checker=mod(floor(vWorld.x*2.)+floor(vWorld.y*2.),2.);
    vec3 base=mix(uColor.rgb,mix(vec3(.76,.81,.71),vec3(.69,.76,.64),checker),uChecker);
    color=vec4(base*light,1.);}`));
  gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));
  this.program=program;this.position=gl.getAttribLocation(program,'aPosition');
  this.model=gl.getUniformLocation(program,'uModel');this.vp=gl.getUniformLocation(program,'uVP');
  this.color=gl.getUniformLocation(program,'uColor');this.checker=gl.getUniformLocation(program,'uChecker');
  this.meshes=new Map(Object.entries(description.meshes).map(([key,m])=>[key,this.buffer(binary(m.vertices,Float32Array),binary(m.triangles,Uint32Array))]));
  this.geoms=description.geoms;
  this.follow=true;this.frameCount=0;this.fpsAt=performance.now();
  this.resetCamera();let dragging=false,lastX=0,lastY=0;
  canvas.addEventListener('pointerdown',e=>{if(e.button!==0)return;dragging=true;lastX=e.clientX;lastY=e.clientY;canvas.setPointerCapture(e.pointerId);});
  canvas.addEventListener('pointermove',e=>{if(!dragging)return;this.azimuth-=(e.clientX-lastX)*.008;this.elevation=Math.max(.35,Math.min(1.45,this.elevation+(e.clientY-lastY)*.008));lastX=e.clientX;lastY=e.clientY;});
  for(const event of ['pointerup','pointercancel'])canvas.addEventListener(event,()=>{dragging=false;});
  canvas.addEventListener('wheel',e=>{e.preventDefault();this.distance=Math.max(.55,Math.min(3,this.distance*Math.exp(e.deltaY*.001)));},{passive:false});
  this.floor=this.buffer(new Float32Array([-30,-30,0,30,-30,0,30,30,0,-30,30,0]),new Uint32Array([0,1,2,0,2,3]));
  gl.enable(gl.DEPTH_TEST);gl.clearColor(.87,.91,.83,1);this.enabled=true;this.lastFrame=0;
  canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();this.enabled=false;canvas.dispatchEvent(new Event('viewfailed'));},{once:true});
  // Use display-aligned pacing; a fixed 33 ms gate skipped refreshes while
  // dragging and made the camera look choppy on otherwise capable devices.
  this.animate=now=>{const interval=1000/60,elapsed=now-this.lastFrame;if(this.enabled&&!document.hidden&&elapsed>=interval-.5){this.lastFrame=now-elapsed%interval;this.draw(now);}this.animation=requestAnimationFrame(this.animate);};
  this.animation=requestAnimationFrame(this.animate);
 }
 resetCamera(){this.azimuth=-.94;this.elevation=1.0;this.distance=1.25;if(this.state)this.anchor=[this.state.robot.x,this.state.robot.y,.08];}
 setFollow(enabled){this.follow=enabled;this.anchor=this.displayTarget?.slice()||[this.state?.robot.x||0,this.state?.robot.y||0,.08];}
 buffer(vertices,indices){const gl=this.gl,v=gl.createBuffer(),i=gl.createBuffer(),vao=gl.createVertexArray();gl.bindVertexArray(vao);gl.bindBuffer(gl.ARRAY_BUFFER,v);gl.bufferData(gl.ARRAY_BUFFER,vertices,gl.STATIC_DRAW);gl.enableVertexAttribArray(this.position);gl.vertexAttribPointer(this.position,3,gl.FLOAT,false,0,0);gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,i);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,indices,gl.STATIC_DRAW);gl.bindVertexArray(null);return {v,i,vao,count:indices.length};}
 drop(mesh){if(!mesh)return;const gl=this.gl;gl.deleteBuffer(mesh.v);gl.deleteBuffer(mesh.i);gl.deleteVertexArray(mesh.vao);}
 walls(maze){
  const key=JSON.stringify([maze.cell,maze.blocked]);if(key===this.wallKey)return;
  this.wallKey=key;const vertices=[],indices=[],corners=[[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]],faces=[0,2,1,0,3,2,4,5,6,4,6,7,0,1,5,0,5,4,2,3,7,2,7,6,1,2,6,1,6,5,3,0,4,3,4,7];
  for(const [x,y] of maze.blocked){const offset=vertices.length/3,cx=(x-1)*maze.cell,cy=(1-y)*maze.cell;for(const [dx,dy,dz] of corners)vertices.push(cx+dx*maze.cell/2,cy+dy*maze.cell/2,.15+dz*.15);for(const f of faces)indices.push(offset+f);}
  this.drop(this.wallMesh);this.wallMesh=this.buffer(new Float32Array(vertices),new Uint32Array(indices));
 }
 update(state){
  if(this.state&&state.robot.sim_time===this.state.robot.sim_time){this.state=state;return;}
  const next=new Map((state.visual_pose||[]).map(row=>[row[0],{p:row.slice(1,4),q:quat(row.slice(4))}]));
  this.previous=this.state&&state.robot.sim_time>=this.state.robot.sim_time?this.current:next;
  this.previousRobot=this.state&&state.robot.sim_time>=this.state.robot.sim_time?this.state.robot:state.robot;
  this.current=next;this.state=state;this.received=performance.now();
 }
 object(mesh,matrix,color,checker=0){const gl=this.gl;gl.bindVertexArray(mesh.vao);gl.uniformMatrix4fv(this.model,false,matrix);gl.uniform4fv(this.color,color);gl.uniform1f(this.checker,checker);gl.drawElements(gl.TRIANGLES,mesh.count,gl.UNSIGNED_INT,0);}
 draw(now){
  if(!this.state)return;const gl=this.gl,c=this.canvas,scale=Math.min(devicePixelRatio||1,1);
  const width=Math.max(1,Math.round(c.clientWidth*scale)),height=Math.max(1,Math.round(c.clientHeight*scale));
  if(c.width!==width||c.height!==height){c.width=width;c.height=height;}gl.viewport(0,0,width,height);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.useProgram(this.program);
  const alpha=clamp((now-this.received)/40),r=this.state.robot,old=this.previousRobot||r;
  const tracked=[old.x+(r.x-old.x)*alpha,old.y+(r.y-old.y)*alpha,.08];
  const target=this.follow?tracked:(this.anchor||tracked);this.displayTarget=target;
  const d=this.distance,e=this.elevation,a=this.azimuth;
  const eye=[target[0]+d*Math.cos(e)*Math.cos(a),target[1]+d*Math.cos(e)*Math.sin(a),target[2]+d*Math.sin(e)];gl.uniformMatrix4fv(this.vp,false,multiply(perspective(width/height),viewMatrix(eye,target)));
  this.object(this.floor,transform([0,0,0],[0,0,0,1]),[1,1,1,1],1);
  this.walls(this.state.maze);this.object(this.wallMesh,transform([0,0,0],[0,0,0,1]),[.54,.65,.46,1]);
  for(const geom of this.geoms){const b=this.current.get(geom.id);if(!b)continue;const a=this.previous?.get(geom.id)||b;
   const p=b.p.map((v,i)=>a.p[i]+alpha*(v-a.p[i])),sign=dot(a.q,b.q)<0?-1:1,q=norm(b.q.map((v,i)=>a.q[i]+alpha*(v*sign-a.q[i])));
   this.object(this.meshes.get(geom.mesh),transform(p,q),geom.color);
  }
  c.dataset.frames=String((Number(c.dataset.frames)||0)+1);
  this.frameCount++;if(now-this.fpsAt>=1000){c.dataset.fps=String(Math.round(this.frameCount*1000/(now-this.fpsAt)));this.frameCount=0;this.fpsAt=now;}
 }
 dispose(){this.enabled=false;cancelAnimationFrame(this.animation);for(const mesh of [...this.meshes.values(),this.floor,this.wallMesh])this.drop(mesh);this.gl.deleteProgram(this.program);}
}
