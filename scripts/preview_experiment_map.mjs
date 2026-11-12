#!/usr/bin/env node
/** Native Excalidraw SVG export and Chromium screenshots for visual inspection. */
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import http from 'node:http';
import {createRequire} from 'node:module';

const args=process.argv.slice(2);
if(args.includes('--help') || args.length<2){
 console.log('Usage: node preview_experiment_map.mjs INPUT.excalidraw OUTPUT_DIR --runtime-dir NODE_RUNTIME [--browser CHROMIUM_PATH] [--viewport-width 1440]');
 console.log('Runtime dependencies: @excalidraw/excalidraw, react, react-dom, esbuild, playwright. Uses native exportToSvg; never draws an approximate replacement.');
 process.exit(args.includes('--help')?0:2);
}
const input=path.resolve(args[0]),output=path.resolve(args[1]);
const option=(name)=>{const i=args.indexOf(name);return i<0?null:args[i+1];};
if(!option('--runtime-dir'))throw new Error('--runtime-dir is required; install preview dependencies in a reusable temporary directory.');
const viewportWidth=Number(option('--viewport-width')||1800);
if(!Number.isInteger(viewportWidth)||viewportWidth<640||viewportWidth>8192)throw new Error('--viewport-width must be an integer from 640 to 8192.');
const runtime=path.resolve(option('--runtime-dir'));
const requireRuntime=createRequire(path.join(runtime,'package.json'));
const {chromium}=requireRuntime('playwright');
const esbuild=requireRuntime('esbuild');
const excalidraw=requireRuntime.resolve('@excalidraw/excalidraw');
let excalidrawRoot=path.dirname(excalidraw);
while(true){
 try{const p=JSON.parse(await fs.readFile(path.join(excalidrawRoot,'package.json'),'utf8'));if(p.name==='@excalidraw/excalidraw')break;}catch{}
 const parent=path.dirname(excalidrawRoot);if(parent===excalidrawRoot)throw new Error('Cannot locate Excalidraw asset root');excalidrawRoot=parent;
}
const buildRoot=await fs.mkdtemp(path.join(os.tmpdir(),'journal-map-render-'));
const scene=JSON.parse(await fs.readFile(input,'utf8'));
await fs.mkdir(output,{recursive:true});
await esbuild.build({stdin:{contents:`import {exportToSvg,restoreElements} from ${JSON.stringify(excalidraw)};
window.EXCALIDRAW_ASSET_PATH='/assets/';
window.renderScene=async(scene)=>{
 const elements=restoreElements(scene.elements,null);
 const svg=await exportToSvg({elements,appState:{...scene.appState,exportBackground:true,viewBackgroundColor:'#ffffff',exportWithDarkMode:false},files:scene.files||{},exportPadding:40});
 document.body.replaceChildren(svg);window.nativeSVG=svg.outerHTML;
 return {width:svg.getAttribute('width'),height:svg.getAttribute('height'),elements:elements.length};
};`,resolveDir:runtime,loader:'js'},bundle:true,format:'esm',outfile:path.join(buildRoot,'bundle.js'),loader:{'.woff2':'file','.woff':'file','.ttf':'file','.png':'file','.svg':'file'},logLevel:'silent'});
const server=http.createServer(async(req,res)=>{
 try{
  const url=new URL(req.url,'http://localhost');
  if(url.pathname==='/'){res.setHeader('Content-Type','text/html; charset=utf-8');res.end('<html><head><meta charset="utf-8" /></head><body style="margin:0;background:white"><script type="module" src="/bundle.js"></script></body></html>');return;}
  if(url.pathname==='/favicon.ico'){res.writeHead(204);res.end();return;}
  const base=url.pathname.startsWith('/assets/')?path.join(excalidrawRoot,'dist/prod'):buildRoot;
  const relative=url.pathname.startsWith('/assets/')?url.pathname.slice('/assets/'.length):url.pathname.slice(1);
  const file=path.resolve(base,decodeURIComponent(relative));
  if(!file.startsWith(base+path.sep)){res.writeHead(403);res.end();return;}
  res.setHeader('Content-Type',({'.js':'text/javascript','.woff2':'font/woff2','.woff':'font/woff','.ttf':'font/ttf'})[path.extname(file)]||'application/octet-stream');
  res.end(await fs.readFile(file));
 }catch{res.writeHead(404);res.end();}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
let browser,browserTemp;
let tempPathMode='native';
try{
 const browserEnv={...process.env};
 if(process.platform==='linux' && await fs.access('/proc/self/fd').then(()=>true,()=>false)){
  // Chromium's SingletonSocket has a short Unix-domain path limit. Keep its
  // temporary files in the configured tree, but expose a short directory handle
  // for the browser's lifetime rather than requiring a per-project wrapper.
  browserTemp=await fs.open(buildRoot,'r');
  browserEnv.TMPDIR=`/proc/${process.pid}/fd/${browserTemp.fd}`;
  tempPathMode='proc-fd';
 }
 browser=await chromium.launch({headless:true,env:browserEnv,...(option('--browser')?{executablePath:path.resolve(option('--browser'))}:{})});
 const page=await browser.newPage({viewport:{width:viewportWidth,height:1100},deviceScaleFactor:1});
 const errors=[],warnings=[];
 page.on('pageerror',e=>errors.push(String(e)));
 page.on('console',m=>{if(m.type()==='error'||m.type()==='warning')warnings.push(m.text());});
 await page.goto(`http://127.0.0.1:${server.address().port}`);
 await page.waitForFunction(()=>!!window.renderScene,{timeout:60000});
 const info=await page.evaluate(s=>window.renderScene(s),scene);
 await page.evaluate(()=>document.fonts.ready);
 await fs.writeFile(path.join(output,'native.svg'),await page.evaluate(()=>window.nativeSVG));
 await page.screenshot({path:path.join(output,'full.png'),fullPage:true});
 await page.screenshot({path:path.join(output,'detail-top.png')});
 await page.evaluate(width=>{const s=document.querySelector('svg');s.style.width=`${width-40}px`;s.style.height='auto';},viewportWidth);
 await page.screenshot({path:path.join(output,'overview.png'),fullPage:true});
 const result={input,renderer:'@excalidraw/excalidraw exportToSvg + Chromium',tempPathMode,viewportWidth,...info,errors,warnings};
 await fs.writeFile(path.join(output,'render.json'),JSON.stringify(result,null,2)+'\n');
 console.log(JSON.stringify(result));if(errors.length)process.exitCode=1;
}finally{
 if(browser)await browser.close();if(browserTemp)await browserTemp.close();await new Promise(resolve=>server.close(resolve));await fs.rm(buildRoot,{recursive:true,force:true});
}
