/* Automated tests use an isolated headless browser, never the user's browser. */
const {chromium}=require(process.env.MISSION_PLAYWRIGHT || 'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
async function main(){
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const base=process.env.MISSION_TEST_URL||'http://127.0.0.1:8766';
 await page.goto(base);await page.getByText('Controller connected',{exact:true}).waitFor();
 await page.screenshot({path:'docs/dashboard-desktop.png',fullPage:true});
 await page.getByRole('button',{name:'02 Voice & gestures'}).click();
 await page.getByPlaceholder('Jumper, say hello').fill('Jumper say hello');
 await page.getByRole('button',{name:'Send',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#mode').textContent==='wave');
 await page.keyboard.press('Escape');
 await page.waitForFunction(()=>document.querySelector('#mode').textContent==='locomotion');
 await page.getByRole('button',{name:'04 Focus companion'}).click();
 await page.getByRole('button',{name:'12s demo'}).click();
 await page.getByRole('button',{name:'Start focus',exact:true}).click();
 await page.getByRole('button',{name:'Pause',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#focus-state').textContent.startsWith('Paused'));
 const paused=await page.locator('#countdown').textContent();
 await page.waitForTimeout(1100);assert.equal(await page.locator('#countdown').textContent(),paused);
 await page.getByRole('button',{name:'Resume',exact:true}).click();
 await page.screenshot({path:'docs/dashboard-focus.png',fullPage:true});
 await page.keyboard.press('Escape');
 await page.getByRole('button',{name:'05 Crab Says'}).click();
 await page.getByRole('button',{name:'New game',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#game-cue').textContent.startsWith('Watch:'));
 const cue=(await page.locator('#game-cue').textContent()).split(': ')[1];
 await page.waitForFunction(()=>document.querySelector('#game-cue').textContent==='Your turn');
 await page.getByRole('button',{name:cue,exact:true}).click();
 await page.getByText('You remembered! ✦',{exact:true}).waitFor();
 await page.keyboard.press('Escape');
 await page.getByRole('button',{name:'01 Mission control'}).click();
 await page.getByRole('button',{name:'Start mission ↗'}).click();
 await page.waitForFunction(()=>document.querySelector('#nav-status').textContent==='running');
 await page.waitForTimeout(800);await page.keyboard.press('Escape');
 await page.waitForFunction(()=>document.querySelector('#nav-status').textContent==='idle');
 // Rapid commands followed by Stop cannot leave a queued expression active.
 await page.getByRole('button',{name:'03 Expressions'}).click();
 await page.locator('[data-action="wave"]').click();
 await page.locator('[data-action="celebrate"]').click();
 await page.keyboard.press('Escape');
 await page.waitForFunction(()=>document.querySelector('#mode').textContent==='locomotion'&&document.querySelector('#queued').textContent==='0');
 // Reset lowers robot time: stale snapshots must not freeze subsequent UI updates.
 await page.locator('[data-action="reset"]').click();
 await page.locator('[data-action="wave"]').click();
 await page.waitForFunction(()=>document.querySelector('#mode').textContent==='wave');
 await page.keyboard.press('Escape');
 // Verify local MediaPipe runtime and model actually load and run one image.
 const media=await page.evaluate(async()=>{
   const {FilesetResolver,HandLandmarker}=await import('/vendor/vision/vision_bundle.mjs');
   const files=await FilesetResolver.forVisionTasks('/vendor/vision/wasm');
   const model=await HandLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:'/vendor/hand_landmarker.task'},runningMode:'IMAGE',numHands:1});
   const blank=document.createElement('canvas');blank.width=640;blank.height=480;
   blank.getContext('2d').fillRect(0,0,640,480);
   const result=model.detect(blank);model.close();return result.landmarks.length;
 });assert.equal(media,0);
 // A permission/device response arriving after Stop must not reactivate camera.
 await page.getByRole('button',{name:'02 Voice & gestures'}).click();
 await page.evaluate(()=>{
   window.testCameraRequested=false;window.testCameraStopped=false;
   navigator.mediaDevices.getUserMedia=()=>{window.testCameraRequested=true;return new Promise(resolve=>{
     window.releaseTestCamera=()=>resolve({getTracks:()=>[{stop:()=>{window.testCameraStopped=true;}}]});
   });};
 });
 await page.locator('#camera').click();
 await page.waitForFunction(()=>window.testCameraRequested);
 await page.keyboard.press('Escape');
 await page.evaluate(()=>window.releaseTestCamera());
 await page.waitForFunction(()=>window.testCameraStopped&&!document.querySelector('#camera').disabled);
 assert.equal(await page.locator('#camera-status').textContent(),'Off');
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:'docs/dashboard-mobile.png',fullPage:true});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
 assert.deepEqual(errors,[]);
 fs.writeFileSync('docs/ui-results.json',JSON.stringify({passed:true,tests:['desktop dashboard','typed voice routing','Escape cancellation','focus pause/resume','memory-game answer','mission start/stop','rapid expression stop','reset followed by command','local MediaPipe blank-frame inference','late camera response after Stop','mobile overflow'],pageErrors:errors,mediaPipeBlankFrameHands:media},null,2));
 await browser.close();console.log('11 UI integration checks passed; no page errors.');
}
main().catch(e=>{console.error(e);process.exit(1)});
