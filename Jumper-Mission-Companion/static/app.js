const $=s=>document.querySelector(s);
let config, state, online=false, lastTime=-1, stream=null, handModel=null;
let cameraOn=false, cameraBusy=false, lastVideo=-1, lastDetection=0;
let cameraSequence=0;
let recognition=null, listening=false, speechSequence=0;
let lastLogKey='', latestVersion=-1;
let nativeView=null,activeView='browser',viewGeneration=0;
let connectionError=false;
let handWorker=null,handJobId=0;const handJobs=new Map();
let speechTranscript='',focusAudio=null,lastFocusCount=null,focusHistoryKey='';
let voiceStage='';
const symbolNames={wave:'Wave',bow:'Bow',paw:'Paw',salute:'Salute'};
function notice(message){$('#alert').textContent=message;$('#alert').hidden=!message;}
async function command(action,payload={}){
  if(!config)throw Error('Controller is not connected');
  const started=performance.now(),visible=!['heartbeat','landmarks'].includes(action);
  if(visible)text('#command-status',`Sending ${action.replaceAll('_',' ')}…`);
  const response=await fetch('/api/command',{method:'POST',signal:AbortSignal.timeout(10000),headers:{'Content-Type':'application/json','X-Mission-Token':config.token},body:JSON.stringify({action,payload})});
  const result=await response.json();
  if(!response.ok){if(visible)text('#command-status','Command rejected');throw Error(result.error||`Request failed (${response.status})`);}
  if(visible)text('#command-status',`${action.replaceAll('_',' ')} accepted · ${Math.round(performance.now()-started)} ms`);
  render(result);return result;
}
async function act(action,payload={}){
  try{notice('');return await command(action,payload);}catch(e){text('#command-status','Command could not complete');notice(e.message);}
}
function text(selector,value){const element=$(selector),next=String(value);if(element.textContent!==next)element.textContent=next;}
function formatTime(seconds){const n=Math.max(0,Math.ceil(seconds));return `${Math.floor(n/60).toString().padStart(2,'0')}:${(n%60).toString().padStart(2,'0')}`;}
function render(s){
  if(!config)return;
  // A reset can reduce simulation time; use monotonic server revisions instead.
  if(s.revision!==undefined){if(s.revision<latestVersion)return;latestVersion=s.revision;}
  else if(s.time<lastTime)return;
  state=s;lastTime=s.time;
  if(cameraOn&&!s.camera_enabled)disableCamera(false);
  if(s.fault)notice(s.fault);
  else if(s.render_error)notice(`Robot view unavailable: ${s.render_error}. Controls remain available.`);
  text('#activity',s.activity[0].toUpperCase()+s.activity.slice(1));
  text('#emotion',s.expression.label);text('#mode',s.robot.mode.replaceAll('_',' '));
  text('#policy',s.robot.running?'Policy running':'Pose transition');
  text('#simtime',`${s.robot.sim_time.toFixed(1)}s`);
  text('#nav-status',s.navigation.status);text('#replans',s.navigation.replans);
  text('#queued',s.expression.queued);
  const input=s.inputs||{},voice=input.voice||{},sign=input.gesture||{};
  $('#voice-feedback').dataset.phase=voiceStage||voice.phase||'idle';
  $('#gesture-feedback').dataset.phase=sign.phase||'off';
  text('#heard-text',voiceStage==='listening'?(speechTranscript||'Listening…'):(speechTranscript||voice.heard||'Nothing heard yet'));
  text('#voice-result',({listening:'Listening. No command is sent until you finish the phrase.',sending:'Checking what you said…',empty:'No final phrase was received. Click Enable voice to try again, or type a command.',error:'The microphone did not deliver a command. Check the message above or use typed commands.'})[voiceStage]||voice.message||'Say one supported command.');
  $('#voice-confirm').hidden=voiceStage!==''||voice.phase!=='confirm';$('#voice-confirm').dataset.id=voice.id;
  text('#hand-label',sign.message||'Enable camera to show a sign.');$('#gesture-progress').value=sign.progress||0;
  const modeNames={gesture_hello:'Waving hello',gesture_bow:'Bowing',gesture_paw:'Offering a paw',gesture_salute:'Saluting',dance_crab:'Celebrating',wave:'Waving hello',bow:'Bowing',paw:'Offering a paw',salute:'Saluting',celebrate:'Celebrating'};
  text('#input-robot-status',s.fault?'Robot needs reset':s.expression.active?(s.robot.running?(modeNames[s.robot.mode]||'Performing the command'):'Moving safely into the starting pose'):s.expression.queued?'Command queued; waiting for the robot':s.robot.mode==='locomotion'?'Robot ready':(modeNames[s.robot.mode]||'Robot moving'));
  const p=s.performance||{};
  text('#sim-speed',p.real_time_factor===undefined?'Measuring speed…':`Simulation ${p.real_time_factor.toFixed(2)}× real time · ${p.view_mode||'Balanced'} view`);
  text('#motion-phase',s.expression.active?(s.robot.running?'Performing motion':'Moving into start pose'):s.expression.queued?'Waiting for controller':'Ready');
  text('#robot-position',`x ${s.robot.x.toFixed(2)} · y ${s.robot.y.toFixed(2)}`);
  const f=s.focus;
  $('.timer').dataset.phase=f.state;
  text('#countdown',formatTime(f.remaining??f.focus_seconds));
  text('#focus-state',({idle:f.last_event==='break_complete'?'Session finished':'Ready when you are',focus:'Focus time · work on your task',paused:'Paused · your time is safe',break:'Break time · focus completed'})[f.state]);
  $('#focus-progress').value=f.progress||0;
  const focusMessage=f.state==='focus'?`Work on “${f.task||'your task'}”. Jumper greets you, then stays quiet while the countdown runs.`:f.state==='paused'?`Your ${f.paused_phase==='break'?'break':'focus'} countdown is paused. Resume when ready, or end the session.`:f.state==='break'?'Your focus session is complete. Jumper celebrates during the break. Take a rest; the next focus session needs your Start.':f.last_event==='break_complete'?'Focus and break are finished. Your session is recorded below. Start another when you are ready.':f.last_event==='cancelled'?'Session ended. Choose a task and start again when ready.':'Choose a preset or try the 12-second demo to see the full flow.';
  text('#focus-explainer',focusMessage);
  if(lastFocusCount!==null&&f.sessions>lastFocusCount&&$('#focus-chime').checked)playFocusChime();lastFocusCount=f.sessions;
  text('#sessions',`${f.sessions} focus sessions completed`);
  document.querySelector('[data-action="focus_start"]').disabled=f.state!=='idle';
  document.querySelector('[data-action="focus_pause"]').disabled=!['focus','break'].includes(f.state);
  document.querySelector('[data-action="focus_resume"]').disabled=f.state!=='paused';
  $('#save-timer').disabled=f.state!=='idle';$('#demo-timer').disabled=f.state!=='idle';
  document.querySelector('[data-action="focus_stop"]').disabled=f.state==='idle';
  document.querySelector('[data-action="focus_skip_break"]').disabled=f.state!=='break';
  for(const id of ['#focus-min','#break-min','#focus-task'])$(id).disabled=f.state!=='idle';
  document.querySelectorAll('[data-preset]').forEach(b=>{b.disabled=f.state!=='idle';const [work,rest]=b.dataset.preset.split(',').map(Number);b.setAttribute('aria-pressed',String(work*60===f.focus_seconds&&rest*60===f.break_seconds));});
  const historyKey=JSON.stringify(f.history||[]);if(historyKey!==focusHistoryKey){focusHistoryKey=historyKey;const list=$('#focus-history');list.replaceChildren();if(!f.history?.length)list.textContent='No completed sessions yet.';for(const item of f.history||[]){const row=document.createElement('p');row.textContent=`✓ ${item.task} · ${formatTime(item.seconds)} focused`;list.append(row);}}
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
  else if(activeView==='map')drawMaze(s,$('#physics-map'));
  if(nativeView)nativeView.update(s);
}
function drawMaze(s,canvas=$('#maze')){
  const ctx=canvas.getContext('2d'),m=s.maze;
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
  document.querySelectorAll('.nav').forEach(b=>{b.classList.toggle('active',b===button);if(b===button)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
  text('#current-panel',button.querySelector('span').textContent);
  document.querySelectorAll('[data-panel]').forEach(p=>p.hidden=p.dataset.panel!==button.dataset.tab);
  if(window.matchMedia('(max-width: 720px)').matches)requestAnimationFrame(()=>{
    window.scrollTo({top:window.scrollY+$('#activity-controls').getBoundingClientRect().top-84,behavior:'instant'});
  });
}));
document.querySelectorAll('[data-action]').forEach(b=>b.addEventListener('click',()=>{if(b.dataset.action==='focus_start'){prepareFocusAudio();act('focus_start',focusSettings());}else act(b.dataset.action);}));
document.querySelectorAll('[data-answer]').forEach(b=>b.addEventListener('click',()=>act(b.dataset.answer)));
function stopVoice(){speechSequence++;if(recognition)recognition.abort();listening=false;voiceStage='';$('#voice-language').disabled=false;$('#mic').disabled=false;text('#mic','🎙 Enable voice');text('#mic-status','Off');}
async function stopAll(){stopVoice();const stopped=act('stop');disableCamera(false);await stopped;}
$('#stop').addEventListener('click',stopAll);
document.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();stopAll();}});
$('#voice-form').addEventListener('submit',e=>{e.preventDefault();speechTranscript='';voiceStage='';act('voice',{text:$('#voice-text').value,confidence:1});});
$('#voice-confirm').addEventListener('click',()=>act('voice_confirm',{id:Number($('#voice-confirm').dataset.id)}));
document.querySelectorAll('[data-phrase]').forEach(b=>b.addEventListener('click',()=>{$('#voice-text').value=b.dataset.phrase;speechTranscript='';voiceStage='';act('voice',{text:b.dataset.phrase,confidence:1});}));
function focusSettings(){return {focus:Number($('#focus-min').value)*60,rest:Number($('#break-min').value)*60,task:$('#focus-task').value};}
function prepareFocusAudio(){if(!$('#focus-chime').checked)return;try{focusAudio??=new(window.AudioContext||window.webkitAudioContext)();focusAudio.resume().catch(()=>{});}catch(e){notice('Sound is unavailable; the visual timer will still work.');}}
function playFocusChime(){if(!focusAudio)return;const start=focusAudio.currentTime;for(const [i,hz] of [660,880].entries()){const tone=focusAudio.createOscillator(),gain=focusAudio.createGain();tone.frequency.value=hz;gain.gain.setValueAtTime(0,start+i*.18);gain.gain.linearRampToValueAtTime(.12,start+i*.18+.02);gain.gain.exponentialRampToValueAtTime(.001,start+i*.18+.16);tone.connect(gain);gain.connect(focusAudio.destination);tone.start(start+i*.18);tone.stop(start+i*.18+.18);}}
document.querySelectorAll('[data-preset]').forEach(b=>b.addEventListener('click',()=>{const [focus,rest]=b.dataset.preset.split(',').map(Number);$('#focus-min').value=focus;$('#break-min').value=rest;act('configure_focus',focusSettings());}));
$('#save-timer').addEventListener('click',()=>act('configure_focus',focusSettings()));
$('#demo-timer').addEventListener('click',()=>{$('#focus-min').value=.2;$('#break-min').value=.1;prepareFocusAudio();act('focus_start',focusSettings());});
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
  recognition=new Speech();recognition.lang=$('#voice-language').value;recognition.interimResults=true;recognition.continuous=false;recognition.maxAlternatives=3;
  const sequence=++speechSequence;
  speechTranscript='';voiceStage='listening';$('#mic').disabled=true;$('#voice-language').disabled=true;text('#mic-status','Starting microphone…');
  recognition.onstart=()=>{if(sequence!==speechSequence)return;listening=true;$('#mic').disabled=false;text('#mic','Finish listening');text('#mic-status','Listening · say one command');};
  recognition.onresult=e=>{if(sequence!==speechSequence)return;for(let i=e.resultIndex;i<e.results.length;i++){speechTranscript=e.results[i][0].transcript;text('#heard-text',speechTranscript);if(e.results[i].isFinal){voiceStage='sending';const alternatives=Array.from(e.results[i]).slice(0,3).map(item=>({text:item.transcript,confidence:Number.isFinite(item.confidence)?item.confidence:0}));$('#voice-text').value=speechTranscript;act('voice',{alternatives}).then(r=>{if(sequence===speechSequence){voiceStage=r?'':'error';if(r)speechTranscript=r.inputs.voice.heard;}});}}};
  recognition.onerror=e=>{if(sequence!==speechSequence)return;voiceStage='error';const message={'not-allowed':'Microphone permission was denied. Allow it in browser site settings or type a command.','no-speech':'No speech was heard. Click Enable voice and try one short command.','network':'The browser speech service could not connect. Typed commands still work.','audio-capture':'No microphone is available. Check the selected Windows input device.'}[e.error]||`Speech recognition stopped: ${e.error}. Typed commands still work.`;notice(message);};
  recognition.onend=()=>{if(sequence!==speechSequence)return;if(voiceStage==='listening')voiceStage='empty';listening=false;$('#voice-language').disabled=false;$('#mic').disabled=false;text('#mic','🎙 Enable voice');text('#mic-status','Off · click to speak again');};
  try{recognition.start();}catch(e){voiceStage='error';$('#voice-language').disabled=false;$('#mic').disabled=false;text('#mic-status','Off');notice(e.message);}
});
async function disableCamera(notifyServer=true){
  cameraSequence++;
  cameraOn=false;if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}
  $('#camera-video').srcObject=null;$('#camera-video').hidden=true;
  $('#camera-stage').hidden=true;text('#hand-presence','Camera off');drawHand([]);
  text('#camera','Enable hand camera');text('#camera-status','Off');
  if(config&&notifyServer)await act('camera_enable',{enabled:false});
}
async function loadHandProcessor(){
 if(handWorker||handModel)return;
 try{
  if(!window.OffscreenCanvas)throw Error('Worker canvas unavailable');
  handWorker=new Worker('/hand-worker.js');
  await new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>reject(Error('Local recognition startup timed out')),20000);
   handWorker.onmessage=({data})=>{
    if(data.type==='ready'){clearTimeout(timer);resolve();}
    else if(data.id!==undefined){const job=handJobs.get(data.id);if(job){handJobs.delete(data.id);clearTimeout(job.timer);data.type==='error'?job.reject(Error(data.message)):job.resolve(data.points);}}
    else if(data.type==='error'){clearTimeout(timer);reject(Error(data.message));}
   };
   handWorker.onerror=()=>{clearTimeout(timer);reject(Error('Local recognition worker failed'));for(const job of handJobs.values()){clearTimeout(job.timer);job.reject(Error('Local recognition interrupted'));}handJobs.clear();};
   handWorker.postMessage({type:'init'});
  });
 }catch(e){
  handWorker?.terminate();handWorker=null;
  const {FilesetResolver,HandLandmarker}=await import('/vendor/vision/vision_bundle.mjs');
  const files=await FilesetResolver.forVisionTasks('/vendor/vision/wasm');
  handModel=await HandLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:'/vendor/hand_landmarker.task'},runningMode:'VIDEO',numHands:1,minHandDetectionConfidence:.7,minHandPresenceConfidence:.7,minTrackingConfidence:.7});
 }
}
async function handPoints(video,timestamp){
 if(!handWorker){const r=handModel.detectForVideo(video,timestamp);return r.landmarks[0]?.map(p=>({x:1-p.x,y:p.y,z:p.z}))||[];}
 const bitmap=await createImageBitmap(video);if(!cameraOn){bitmap.close();return [];}
 const id=++handJobId;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{handJobs.delete(id);reject(Error('Local hand recognition timed out'));},5000);handJobs.set(id,{resolve,reject,timer});handWorker.postMessage({type:'frame',id,bitmap,timestamp},[bitmap]);});
}
$('#camera').addEventListener('click',async()=>{
  if(cameraOn){await disableCamera();return;}
  const sequence=++cameraSequence;
  $('#camera').disabled=true;
  try{
    text('#camera-status','Loading local hand model…');
    await loadHandProcessor();
    if(sequence!==cameraSequence)return;
    const acquired=await navigator.mediaDevices.getUserMedia({video:{width:640,height:480},audio:false});
    if(sequence!==cameraSequence){acquired.getTracks().forEach(t=>t.stop());return;}
    stream=acquired;
    const video=$('#camera-video');video.srcObject=stream;video.hidden=false;$('#camera-stage').hidden=false;await video.play();
    if(sequence!==cameraSequence)return;
    await command('camera_enable',{enabled:true});
    if(sequence!==cameraSequence){await act('camera_enable',{enabled:false});return;}
    cameraOn=true;lastVideo=-1;
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
      const points=await handPoints(video,now);if(!cameraOn)return;
      drawHand(points);text('#hand-presence',points.length?'Hand tracked · watch the hold bar below':'No hand tracked · move your whole hand into frame');
      await command('landmarks',{points});
    }catch(e){notice(`Hand recognition: ${e.message}`);await disableCamera();}
    finally{cameraBusy=false;}
  }
  if(cameraOn)requestAnimationFrame(detect);
}
function drawHand(points){const c=$('#hand-overlay'),ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);if(!points.length)return;ctx.strokeStyle='#8beaab';ctx.lineWidth=3;for(const chain of [[0,1,2,3,4],[0,5,6,7,8],[5,9,10,11,12],[9,13,14,15,16],[13,17,18,19,20],[0,17]]){ctx.beginPath();chain.forEach((id,i)=>{const p=points[id];i?ctx.lineTo(p.x*c.width,p.y*c.height):ctx.moveTo(p.x*c.width,p.y*c.height);});ctx.stroke();}ctx.fillStyle='#fff';for(const p of points){ctx.beginPath();ctx.arc(p.x*c.width,p.y*c.height,4,0,Math.PI*2);ctx.fill();}}
document.addEventListener('visibilitychange',()=>{if(!config)return;if(document.hidden){stopVoice();disableCamera();act('ui_hidden');}else act('ui_visible');});
window.addEventListener('pagehide',()=>{if(stream)stream.getTracks().forEach(t=>t.stop());if(recognition)recognition.abort();if(config)fetch('/api/command',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json','X-Mission-Token':config.token},body:JSON.stringify({action:'ui_hidden'})}).catch(()=>{});});
async function poll(){
  if(!config)return;
  try{const r=await fetch('/api/state',{signal:AbortSignal.timeout(5000)});const snapshot=await r.json();if(!config)return;if(!r.ok)throw Error(snapshot.error||'Controller disconnected');if(connectionError){notice('');connectionError=false;}render(snapshot);online=true;$('.connection').dataset.state='online';text('#connection','Controller connected');}
  catch(e){if(!config)return;online=false;connectionError=true;$('.connection').dataset.state='offline';text('#connection','Disconnected');notice(e.message);}
  setTimeout(poll,document.hidden?700:(config?.poll_interval_ms||50));
}
async function selectView(mode,notify=true){
  const generation=++viewGeneration;
  if(notify)await command('set_view',{mode});
  activeView=mode;$('#view-choice').value=mode;
  $('#reset-camera').hidden=mode!=='browser';$('#view-hint').hidden=mode!=='browser';
  $('#follow-setting').hidden=mode!=='browser';
  for(const id of ['#native-view','#webgl-view','#physics-map'])$(id).hidden=true;
  if(nativeView)nativeView.enabled=mode==='browser';
  const img=$('#native-view');img.onerror=null;img.removeAttribute('src');
  if(mode==='image'){
    img.hidden=false;img.onerror=()=>{if(activeView==='image')setTimeout(()=>{if(activeView==='image')img.src=`/api/stream?t=${Date.now()}`;},1000);};img.src='/api/stream';
  }else if(mode==='map'){$('#physics-map').hidden=false;if(state)drawMaze(state,$('#physics-map'));}
  else{
    try{
      if(!nativeView){
        text('#command-status','Loading the official robot model…');
        const [{NativeView},description]=await Promise.all([import('/native-view.js'),fetch('/api/scene').then(r=>{if(!r.ok)throw Error('Robot geometry unavailable');return r.json();})]);
        if(generation!==viewGeneration)return;
        nativeView=new NativeView($('#webgl-view'),description);
        nativeView.setFollow($('#follow-crab').checked);
        $('#webgl-view').addEventListener('viewfailed',()=>{nativeView?.dispose();nativeView=null;notice('3D graphics were interrupted. Switched to the live 2D view.');selectView('map').catch(e=>notice(e.message));},{once:true});
      }
      if(generation!==viewGeneration)return;
      nativeView.enabled=true;$('#webgl-view').hidden=false;if(state)nativeView.update(state);
      text('#command-status','Ready for a command');
    }catch(e){notice(`${e.message} Showing actual physics in 2D.`);await selectView('map');}
  }
}
$('#view-choice').addEventListener('change',()=>selectView($('#view-choice').value).catch(e=>notice(e.message)));
$('#reset-camera').addEventListener('click',()=>nativeView?.resetCamera());
$('#follow-crab').addEventListener('change',()=>nativeView?.setFollow($('#follow-crab').checked));
try{
  const response=await fetch('/api/config');
  let received;
  try{received=await response.json();}
  catch{throw Error(response.ok?'The server returned an incomplete response. Reload to reconnect.':`The robot server is unavailable (HTTP ${response.status}). It may be restarting. Please try again shortly.`);}
  if(!response.ok)throw Error(received.error||'The simulation could not start.');
  config=received;
  if(config.hosted){
    $('#hosted-notice').hidden=false;
    text('#hosted-details',`Your browser has a separate robot. History resets when the server restarts. Sessions last up to ${Math.round(config.session_lifetime_seconds/60)} minutes. Release the robot when finished so another visitor can use it.`);
    $('.aside-badge').lastChild.textContent=' YOUR HOSTED COMPANION';
  }
  const native=config.backend==='native';$('#preview-view').hidden=native;
  text('#backend-label',native?'MuJoCo · official model':'Kinematic preview');
  text('#stage-note',native?'Official Jumper model + stock ONNX policies. Independent native host; physical hardware untested.':'Explicit kinematic preview. Positions and gestures are schematic, not physics validation.');
  text('#map-hint','Click a cell to add or remove an obstacle. The route replans; the robot and goal stay protected.');
  if(native){$('#view-settings').hidden=false;text('#build-version',`v${config.version||'unknown'}`);$('#view-choice option[value="image"]').disabled=!config.image_available;await selectView(config.view||'browser',false);}
  await command('heartbeat');poll();
  setInterval(()=>{if(config&&!document.hidden)command('heartbeat').catch(()=>{});},700);
}catch(e){
  online=false;text('#connection','Connection failed');$('.connection').dataset.state='offline';
  notice(`Startup failed: ${e.message}`);
}

$('#release-session').addEventListener('click',async()=>{
  if(!config?.hosted)return;
  const button=$('#release-session');button.disabled=true;
  try{
    await stopAll();
    const response=await fetch('/api/session/end',{method:'POST',headers:{'X-Mission-Token':config.token}});
    const result=await response.json();if(!response.ok)throw Error(result.error||'Could not release the session');
    config=null;online=false;if(nativeView)nativeView.enabled=false;notice('Hosted robot released. Start a new session to reconnect.');
    text('#connection','Session released');$('.connection').dataset.state='offline';
    $('#reconnect-session').hidden=false;button.hidden=true;
    document.querySelectorAll('[data-action], [data-answer], [data-preset], [data-phrase], #mic, #camera, #voice-form button, #demo-timer, #save-timer, #stop, #view-choice').forEach(b=>b.disabled=true);
  }catch(e){notice(e.message);button.disabled=false;}
});
$('#reconnect-session').addEventListener('click',()=>window.location.reload());
