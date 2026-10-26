const $=s=>document.querySelector(s);
let config, state, online=false, lastTime=-1, stream=null, handModel=null;
let cameraOn=false, cameraBusy=false, lastVideo=-1, lastDetection=0;
let cameraSequence=0;
let recognition=null, listening=false, speechSequence=0;
let lastLogKey='', latestVersion=-1;
const symbolNames={wave:'Wave',bow:'Bow',paw:'Paw',salute:'Salute'};
function notice(message){$('#alert').textContent=message;$('#alert').hidden=!message;}
async function command(action,payload={}){
  if(!config)throw Error('Controller is not connected');
  const response=await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json','X-Mission-Token':config.token},body:JSON.stringify({action,payload})});
  const result=await response.json();
  if(!response.ok)throw Error(result.error||`Request failed (${response.status})`);
  render(result);return result;
}
async function act(action,payload={}){
  try{notice('');return await command(action,payload);}catch(e){notice(e.message);}
}
function text(selector,value){const element=$(selector),next=String(value);if(element.textContent!==next)element.textContent=next;}
function formatTime(seconds){const n=Math.max(0,Math.ceil(seconds));return `${Math.floor(n/60).toString().padStart(2,'0')}:${(n%60).toString().padStart(2,'0')}`;}
function render(s){
  // A reset can reduce simulation time; use monotonic server revisions instead.
  if(s.revision!==undefined){if(s.revision<latestVersion)return;latestVersion=s.revision;}
  else if(s.time<lastTime)return;
  state=s;lastTime=s.time;
  if(s.fault)notice(s.fault);
  else if(s.render_error)notice(`Robot view unavailable: ${s.render_error}. Controls remain available.`);
  text('#activity',s.activity[0].toUpperCase()+s.activity.slice(1));
  text('#emotion',s.expression.label);text('#mode',s.robot.mode.replaceAll('_',' '));
  text('#policy',s.robot.running?'Policy running':'Pose transition');
  text('#simtime',`${s.robot.sim_time.toFixed(1)}s`);
  text('#nav-status',s.navigation.status);text('#replans',s.navigation.replans);
  text('#queued',s.expression.queued);
  text('#robot-position',`x ${s.robot.x.toFixed(2)} · y ${s.robot.y.toFixed(2)}`);
  const f=s.focus;
  text('#countdown',formatTime(f.remaining??f.focus_seconds));
  text('#focus-state',({idle:'Ready when you are',focus:'Time to focus',paused:'Paused · your time is safe',break:'A well-earned break'})[f.state]);
  text('#sessions',`${f.sessions} focus sessions completed`);
  document.querySelector('[data-action="focus_start"]').disabled=f.state!=='idle';
  document.querySelector('[data-action="focus_pause"]').disabled=f.state!=='focus';
  document.querySelector('[data-action="focus_resume"]').disabled=f.state!=='paused';
  $('#save-timer').disabled=f.state!=='idle';$('#demo-timer').disabled=f.state!=='idle';
  text('#level',s.game.level);text('#best',s.game.best);text('#answered',s.game.answered);
  text('#game-cue',({idle:'Ready to play?',showing:s.game.cue?`Watch: ${symbolNames[s.game.cue]}`:'Watch Jumper…',answering:'Your turn',won:'You remembered! ✦',lost:'Almost! Try a new game.',complete:'All 20 levels complete!'})[s.game.state]);
  document.querySelectorAll('[data-answer]').forEach(b=>b.disabled=s.game.state!=='answering');
  document.querySelector('[data-action="game_next"]').disabled=s.game.state!=='won'||s.expression.active!==null||s.expression.queued>0;
  const latest=s.logs.at(-1);text('#latest-log',latest?latest.message:'Ready');
  const log=$('#full-log'),logKey=JSON.stringify(s.logs);
  if(logKey!==lastLogKey){lastLogKey=logKey;const fragment=document.createDocumentFragment();
  for(const item of s.logs.slice().reverse()){
    const row=document.createElement('div');row.className='log-item';
    const at=document.createElement('time');at.textContent=`${item.at.toFixed(2)}s · ${item.kind}`;
    const msg=document.createElement('span');msg.textContent=item.message;
    row.append(at,msg);fragment.append(row);
  }
  log.replaceChildren(fragment);}
  drawMaze(s);if(config.backend==='preview')drawPreview(s);
}
function drawMaze(s){
  const canvas=$('#maze'),ctx=canvas.getContext('2d'),m=s.maze;
  const size=Math.min(440/m.width,390/m.height),ox=(440-size*m.width)/2,oy=(390-size*m.height)/2;
  canvas.mazeLayout={size,ox,oy};ctx.clearRect(0,0,440,390);
  const blocks=new Set(m.blocked.map(c=>c.join(',')));
  for(let y=0;y<m.height;y++)for(let x=0;x<m.width;x++){
    const wall=blocks.has(`${x},${y}`);ctx.fillStyle=wall?'#cad5bd':'#f4f7ee';
    ctx.beginPath();ctx.roundRect(ox+x*size+2,oy+y*size+2,size-4,size-4,5);ctx.fill();
  }
  const pos=(x,y)=>[ox+(x+0.5)*size,oy+(y+0.5)*size];
  if(s.navigation.path.length){ctx.beginPath();ctx.strokeStyle='#d0ad58';ctx.lineWidth=3;ctx.setLineDash([5,5]);
    ctx.moveTo(...pos(s.robot.x/m.cell+1,1-s.robot.y/m.cell));
    for(const cell of s.navigation.path)ctx.lineTo(...pos(...cell));ctx.stroke();ctx.setLineDash([]);}
  ctx.fillStyle='#c3a151';ctx.beginPath();ctx.arc(...pos(...m.goal),8,0,Math.PI*2);ctx.fill();
  ctx.fillStyle='#fff';ctx.font='12px sans-serif';ctx.textAlign='center';ctx.fillText('✦',...pos(m.goal[0],m.goal[1]+0.09));
  const [rx,ry]=pos(s.robot.x/m.cell+1,1-s.robot.y/m.cell);
  ctx.save();ctx.translate(rx,ry);ctx.rotate(-s.robot.yaw);ctx.fillStyle='#27654b';
  ctx.beginPath();ctx.arc(0,0,10,0,Math.PI*2);ctx.fill();ctx.fillStyle='#fff';ctx.beginPath();ctx.moveTo(6,0);ctx.lineTo(-2,-4);ctx.lineTo(-2,4);ctx.closePath();ctx.fill();ctx.restore();
}
function drawPreview(s){
  const c=$('#preview-view'),x=c.getContext('2d');
  x.fillStyle='#dde6d4';x.fillRect(0,0,c.width,c.height);
  x.strokeStyle='#ced9c4';x.lineWidth=1;
  for(let i=0;i<20;i++){x.beginPath();x.moveTo(i*70,0);x.lineTo(i*70,600);x.stroke();x.beginPath();x.moveTo(0,i*70);x.lineTo(900,i*70);x.stroke();}
  x.save();x.translate(450,300);x.rotate(-s.robot.yaw);
  const moving=s.robot.mode!=='locomotion',w=moving?Math.sin(s.time*5)*16:0;
  x.lineCap='round';x.strokeStyle='#536a42';x.lineWidth=14;
  for(const side of [-1,1])for(let i=0;i<3;i++){
    x.beginPath();x.moveTo(side*57,(i-1)*29);x.lineTo(side*(110+i*5),(i-1)*67+w);x.lineTo(side*(138-i*8),(i-1)*80+22);x.stroke();}
  x.fillStyle='#75945d';x.beginPath();x.roundRect(-72,-70,144,140,40);x.fill();
  x.fillStyle='#203f32';x.beginPath();x.roundRect(-52,-40,104,50,16);x.fill();
  x.fillStyle='#ebf4d5';for(const a of [-24,24]){x.beginPath();x.ellipse(a,-15,5,10,0,0,7);x.fill();}
  x.restore();x.fillStyle='#63765a';x.font='18px Segoe UI';x.fillText('KINEMATIC PREVIEW · NOT ROBOT PHYSICS',30,45);
}
document.querySelectorAll('.nav').forEach(button=>button.addEventListener('click',()=>{
  document.querySelectorAll('.nav').forEach(b=>b.classList.toggle('active',b===button));
  document.querySelectorAll('[data-panel]').forEach(p=>p.hidden=p.dataset.panel!==button.dataset.tab);
}));
document.querySelectorAll('[data-action]').forEach(b=>b.addEventListener('click',()=>act(b.dataset.action)));
document.querySelectorAll('[data-answer]').forEach(b=>b.addEventListener('click',()=>act(b.dataset.answer)));
async function stopAll(){speechSequence++;if(recognition)recognition.abort();const stopped=act('stop');await disableCamera();await stopped;}
$('#stop').addEventListener('click',stopAll);
document.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();stopAll();}});
$('#voice-form').addEventListener('submit',e=>{e.preventDefault();act('voice',{text:$('#voice-text').value,confidence:1});});
$('#save-timer').addEventListener('click',()=>act('configure_focus',{focus:Number($('#focus-min').value)*60,rest:Number($('#break-min').value)*60}));
$('#demo-timer').addEventListener('click',async()=>{const r=await act('configure_focus',{focus:12,rest:6});if(r){$('#focus-min').value=0.2;$('#break-min').value=0.1;}});
$('#export').addEventListener('click',()=>{
  if(!state)return;const blob=new Blob([JSON.stringify({schema:'mission-session/1',created:new Date().toISOString(),...state},null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='mission-session.json';a.click();URL.revokeObjectURL(url);
});
$('#maze').addEventListener('click',e=>{
  const c=$('#maze'),r=c.getBoundingClientRect(),{size,ox,oy}=c.mazeLayout;
  const x=Math.floor(((e.clientX-r.left)*440/r.width-ox)/size),y=Math.floor(((e.clientY-r.top)*390/r.height-oy)/size);
  act('toggle_obstacle',{x,y});
});
$('#mic').addEventListener('click',()=>{
  const Speech=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!Speech){notice('This browser has no speech-recognition API. Typed commands still work.');return;}
  if(listening){recognition.stop();return;}
  recognition=new Speech();recognition.lang='en-IN';recognition.interimResults=false;recognition.continuous=false;
  const sequence=++speechSequence;
  recognition.onstart=()=>{listening=true;text('#mic','Stop listening');text('#mic-status','Listening…');};
  recognition.onresult=e=>{if(sequence!==speechSequence)return;for(let i=e.resultIndex;i<e.results.length;i++)if(e.results[i].isFinal){const item=e.results[i][0];$('#voice-text').value=item.transcript;act('voice',{text:item.transcript,confidence:item.confidence});}};
  recognition.onerror=e=>notice(`Voice recognition: ${e.error}. You can use typed commands.`);
  recognition.onend=()=>{listening=false;text('#mic','🎙 Enable voice');text('#mic-status','Off');};
  try{recognition.start();}catch(e){notice(e.message);}
});
async function disableCamera(){
  cameraSequence++;
  cameraOn=false;if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}
  $('#camera-video').srcObject=null;$('#camera-video').hidden=true;
  text('#camera','Enable hand camera');text('#camera-status','Off');
  if(config)await act('camera_enable',{enabled:false});
}
$('#camera').addEventListener('click',async()=>{
  if(cameraOn){await disableCamera();return;}
  const sequence=++cameraSequence;
  $('#camera').disabled=true;
  try{
    text('#camera-status','Loading local hand model…');
    if(!handModel){
      const {FilesetResolver,HandLandmarker}=await import('/vendor/vision/vision_bundle.mjs');
      const files=await FilesetResolver.forVisionTasks('/vendor/vision/wasm');
      handModel=await HandLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:'/vendor/hand_landmarker.task'},runningMode:'VIDEO',numHands:1,minHandDetectionConfidence:0.7,minHandPresenceConfidence:0.7,minTrackingConfidence:0.7});
    }
    if(sequence!==cameraSequence)return;
    const acquired=await navigator.mediaDevices.getUserMedia({video:{width:640,height:480},audio:false});
    if(sequence!==cameraSequence){acquired.getTracks().forEach(t=>t.stop());return;}
    stream=acquired;
    const video=$('#camera-video');video.srcObject=stream;video.hidden=false;await video.play();
    if(sequence!==cameraSequence)return;
    cameraOn=true;lastVideo=-1;await command('camera_enable',{enabled:true});
    text('#camera','Disable hand camera');text('#camera-status','On · local detection');
    requestAnimationFrame(detect);
  }catch(e){await disableCamera();notice(`Camera unavailable: ${e.message}`);}
  finally{$('#camera').disabled=false;}
});
async function detect(now){
  if(!cameraOn)return;const video=$('#camera-video');
  if(!cameraBusy&&now-lastDetection>=100&&video.readyState>=2&&video.currentTime!==lastVideo){
    cameraBusy=true;lastDetection=now;lastVideo=video.currentTime;
    try{
      const result=handModel.detectForVideo(video,now);
      const points=result.landmarks[0]?.map(p=>({x:1-p.x,y:p.y,z:p.z}))||[];
      await command('landmarks',{points});
      text('#hand-label',points.length?'Hand detected · hold a deliberate sign':'No hand detected');
    }catch(e){notice(`Hand recognition: ${e.message}`);await disableCamera();}
    finally{cameraBusy=false;}
  }
  if(cameraOn)requestAnimationFrame(detect);
}
document.addEventListener('visibilitychange',()=>{if(document.hidden){speechSequence++;if(recognition)recognition.abort();disableCamera();act('stop');}});
window.addEventListener('pagehide',()=>{if(stream)stream.getTracks().forEach(t=>t.stop());if(recognition)recognition.abort();if(config)fetch('/api/command',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json','X-Mission-Token':config.token},body:JSON.stringify({action:'stop'})}).catch(()=>{});});
async function poll(){
  try{const r=await fetch('/api/state');if(!r.ok)throw Error('Controller disconnected');render(await r.json());online=true;text('#connection','Controller connected');}
  catch(e){online=false;text('#connection','Disconnected');notice(e.message);}
  setTimeout(poll,document.hidden?700:100);
}
try{
  config=await (await fetch('/api/config')).json();
  const native=config.backend==='native';$('#native-view').hidden=!native;$('#preview-view').hidden=native;
  text('#backend-label',native?'MuJoCo · official model':'Kinematic preview');
  text('#stage-note',native?'Official Jumper model + stock ONNX policies. Independent native host; physical hardware untested.':'Explicit kinematic preview. Positions and gestures are schematic, not physics validation.');
  text('#map-hint','Click a cell to add or remove an obstacle. The route replans; the robot and goal stay protected.');
  if(native){
    const img=$('#native-view');let imageTimer;
    const nextImage=()=>{imageTimer=setTimeout(()=>{img.src=`/api/frame?t=${Date.now()}`;},document.hidden?700:80);};
    img.onload=nextImage;img.onerror=nextImage;img.src='/api/frame';
  }
  await command('heartbeat');poll();
  setInterval(()=>{if(!document.hidden)command('heartbeat').catch(()=>{});},700);
}catch(e){notice(`Startup failed: ${e.message}`);}
