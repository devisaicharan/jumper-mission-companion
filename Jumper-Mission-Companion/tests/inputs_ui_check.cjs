const {chromium}=require(process.env.MISSION_PLAYWRIGHT||'playwright');
const assert=require('node:assert/strict'),fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>{
  class TestSpeech{
   constructor(){window.testSpeech=this;}
   start(){this.onstart?.();}
   stop(){this.onend?.();}
   abort(){this.onend?.();}
   emit(text,confidence){const result=[{transcript:text,confidence}];result.isFinal=true;this.onresult?.({resultIndex:0,results:[result]});this.onend?.();}
  }
  window.SpeechRecognition=TestSpeech;
 });
 await page.goto('http://127.0.0.1:8768');await page.getByText('Controller connected',{exact:true}).waitFor();
 await page.getByRole('button',{name:'02 Voice & gestures',exact:true}).click();
 await page.locator('#mic').click();await page.evaluate(()=>window.testSpeech.emit('Hey, hi.',.95));
 await page.waitForFunction(()=>document.querySelector('#mode').textContent==='gesture hello');
 assert.ok((await page.locator('#voice-result').textContent()).includes('Understood'));
 await page.keyboard.press('Escape');await page.waitForFunction(()=>document.querySelector('#mode').textContent==='locomotion');
 await page.locator('#mic').click();await page.evaluate(()=>window.testSpeech.emit('bow',0));
 await page.locator('#voice-confirm').waitFor({state:'visible'});
 assert.equal(await page.locator('#mode').textContent(),'locomotion');
 await page.locator('#voice-confirm').click();await page.waitForFunction(()=>document.querySelector('#mode').textContent==='gesture bow');
 await page.keyboard.press('Escape');await page.waitForFunction(()=>document.querySelector('#mode').textContent==='locomotion');
 await page.locator('#mic').click();await page.evaluate(()=>window.testSpeech.emit('explain how to solve maze',.99));
 await page.waitForFunction(()=>document.querySelector('#voice-result').textContent.includes('No supported command'));
 // Generated landmarks are fed through the authenticated API while the UI
 // displays gate progress. This validates routing, not webcam accuracy.
 const feed=async fingers=>page.evaluate(async fingers=>{
  const config=await(await fetch('/api/config')).json();
  const p=Array.from({length:21},()=>({x:.5,y:.8,z:0}));
  [[5,6,7,8],[9,10,11,12],[13,14,15,16],[17,18,19,20]].forEach((ids,i)=>ids.forEach((id,j)=>{p[id]={x:.35+i*.1,y:(fingers[i]?[.55,.4,.3,.15]:[.55,.4,.5,.6])[j],z:0};}));
  const send=(action,payload={})=>fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json','X-Mission-Token':config.token},body:JSON.stringify({action,payload})});
  await send('camera_enable',{enabled:true});
  for(let i=0;i<9;i++){await send('landmarks',{points:p});await new Promise(resolve=>setTimeout(resolve,90));}
 },fingers);
 await feed([1,1,0,0]);await page.waitForFunction(()=>document.querySelector('#mode').textContent==='gesture hello');
 assert.ok((await page.locator('#hand-label').textContent()).includes('Wave'));
 await feed([1,1,1,1]);await page.waitForFunction(()=>document.querySelector('#mode').textContent==='locomotion');
 const afterPalm=await page.evaluate(async()=>await(await fetch('/api/state')).json());assert.equal(afterPalm.camera_enabled,true);
 await page.screenshot({path:'docs/dashboard-inputs.png',fullPage:true});
 await page.keyboard.press('Escape');
 await page.getByRole('button',{name:'04 Focus companion',exact:true}).click();
 await page.locator('#focus-task').fill('Revise one OS topic');await page.getByRole('button',{name:'12s demo',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#focus-state').textContent.startsWith('Focus time'));
 assert.ok((await page.locator('#focus-explainer').textContent()).includes('Revise one OS topic'));
 await page.waitForFunction(()=>document.querySelector('#focus-state').textContent.startsWith('Break time'),null,{timeout:25000});
 assert.ok((await page.locator('#focus-history').textContent()).includes('Revise one OS topic'));
 await page.getByRole('button',{name:'Pause',exact:true}).click();await page.waitForFunction(()=>document.querySelector('#focus-state').textContent.startsWith('Paused'));
 const paused=await page.locator('#countdown').textContent();await page.waitForTimeout(1200);assert.equal(await page.locator('#countdown').textContent(),paused);
 await page.getByRole('button',{name:'Resume',exact:true}).click();await page.waitForFunction(()=>document.querySelector('#focus-state').textContent.startsWith('Break time'));
 await page.getByRole('button',{name:'Skip break',exact:true}).click();await page.waitForFunction(()=>document.querySelector('[data-action="focus_start"]').disabled===false);
 await page.screenshot({path:'docs/dashboard-focus-improved.png',fullPage:true});
 // Leaving the dashboard preserves only the focus timer, with no robot reward.
 await page.getByRole('button',{name:'12s demo',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#focus-state').textContent.startsWith('Focus time'));
 await page.goto('about:blank');await page.waitForTimeout(19500);
 await page.goto('http://127.0.0.1:8768');await page.getByText('Controller connected',{exact:true}).waitFor();
 const returned=await page.evaluate(async()=>await(await fetch('/api/state')).json());
 assert.equal(returned.focus.sessions,2);assert.equal(returned.focus.state,'idle');assert.equal(returned.robot.mode,'locomotion');
 assert.deepEqual(errors,[]);
 fs.writeFileSync('docs/inputs-ui-results.json',JSON.stringify({passed:true,environment:'generated speech-service events and landmarks routed into native MuJoCo; no real microphone/webcam recording',tests:['greeting speech callback executes native wave','zero-confidence speech requires confirmation before native bow','unmatched speech explains no action','V-sign gate executes native wave','palm stop keeps camera enabled','one-click focus demo applies task','focus completion records task and explains break','break pause preserves time','resume and skip break do not start another session','leaving dashboard preserves focus completion without unattended robot reward'],pageErrors:errors},null,2));
 await browser.close();console.log('10 native input/focus browser checks passed.');
})().catch(e=>{console.error(e);process.exit(1)});
