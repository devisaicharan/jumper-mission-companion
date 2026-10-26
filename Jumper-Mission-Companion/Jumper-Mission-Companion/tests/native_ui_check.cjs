const {chromium}=require(process.env.MISSION_PLAYWRIGHT||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8767');
 await page.getByText('MuJoCo · official model',{exact:true}).waitFor();
 await page.waitForFunction(()=>document.querySelector('#native-view').naturalWidth>0);
 await page.screenshot({path:'docs/dashboard-native.png',fullPage:true});
 await page.getByRole('button',{name:'03 Expressions'}).click();
 await page.getByRole('button',{name:'Joyful',exact:false}).click();
 try{await page.waitForFunction(()=>document.querySelector('#mode').textContent==='dance crab',null,{timeout:15000});}
 catch(e){fs.writeFileSync('docs/native-ui-failure.json',JSON.stringify(await page.evaluate(async()=>await (await fetch('/api/state')).json()),null,2));throw e;}
 await page.keyboard.press('Escape');
 await page.waitForFunction(()=>document.querySelector('#mode').textContent==='locomotion',null,{timeout:10000});
 await page.getByRole('button',{name:'01 Mission control'}).click();
 await page.getByRole('button',{name:'Start mission ↗'}).click();
 await page.waitForFunction(()=>document.querySelector('#nav-status').textContent==='running');
 const snapshot=await page.evaluate(async()=>await (await fetch('/api/state')).json());
 const cell=snapshot.navigation.path[3];
 const box=await page.locator('#maze').boundingBox();
 const size=Math.min(440/snapshot.maze.width,390/snapshot.maze.height);
 const ox=(440-size*snapshot.maze.width)/2,oy=(390-size*snapshot.maze.height)/2;
 await page.locator('#maze').click({position:{x:(ox+(cell[0]+.5)*size)*box.width/440,y:(oy+(cell[1]+.5)*size)*box.height/390}});
 await page.waitForFunction(()=>Number(document.querySelector('#replans').textContent)>=1);
 await page.waitForFunction(()=>document.querySelector('#nav-status').textContent==='complete',null,{timeout:90000});
 await page.screenshot({path:'docs/dashboard-native-complete.png',fullPage:true});
 assert.deepEqual(errors,[]);
 fs.writeFileSync('docs/native-ui-results.json',JSON.stringify({passed:true,tests:['native model frame displayed','celebration routes to actual dance mode','Escape cancels native dance','native mission and live obstacle replan via dashboard'],pageErrors:errors},null,2));
 await browser.close();console.log('4 native UI checks passed.');
})().catch(e=>{console.error(e);process.exit(1)});
