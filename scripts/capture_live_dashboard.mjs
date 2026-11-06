// Read-only production-browser verification. Credentials stay in memory.
import fs from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(new URL('../apps/web/package.json',import.meta.url));
const {chromium}=require('@playwright/test');
const values=Object.fromEntries(fs.readFileSync('.data/live/access.env','utf8').split(/\r?\n/).filter(x=>x.includes('=')).map(x=>{const i=x.indexOf('=');return [x.slice(0,i),x.slice(i+1).replace(/^['"]|['"]$/g,'')];}));
const browser=await chromium.launch();
try {
 const context=await browser.newContext({viewport:{width:1440,height:1100}});
 const login=await context.request.post('http://localhost:3000/api/v1/auth/login',{data:{email:values.APP_EMAIL,password:values.APP_PASSWORD}});
 if(!login.ok()) throw new Error('Live login failed: '+login.status());
 const page=await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 for(const [route,name] of [['/','overview'],['/workflows/'+values.WORKFLOW_ID,'workflow'],['/agents','agents'],['/approvals','approvals']]){
  await page.goto('http://localhost:3000'+route);
  await page.waitForTimeout(1800);
  await page.screenshot({path:'docs/screenshots/live-'+name+'.png',fullPage:true});
 }
 await page.setViewportSize({width:390,height:844});
 await page.goto('http://localhost:3000/');await page.waitForTimeout(1500);
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw new Error('Mobile horizontal overflow');
 await page.screenshot({path:'docs/screenshots/live-mobile.png',fullPage:true});
 if(errors.length)throw new Error(errors.join('\n'));
 console.log('Live production overview, workflow, agents, approvals and 390px layout captured; no browser exceptions.');
}finally{await browser.close();}
