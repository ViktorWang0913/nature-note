import { readdir, readFile, writeFile } from 'node:fs/promises';
import { resolve, relative, join } from 'node:path';
import { createHash } from 'node:crypto';

// 路径
const outputPath=resolve('dist');

// 主程序
const paths=await readdir(outputPath,{recursive:true,withFileTypes:true});
const assets=paths.filter(entry=>entry.isFile()&&entry.name!=='sw.js').map(entry=>'/'+relative(outputPath,join(entry.parentPath,entry.name)).replaceAll('\\','/'));
const version=createHash('sha256').update(await readFile(join(outputPath,'index.html'))).digest('hex').slice(0,16);
const worker=`const cacheName='nature-shell-${version}';
const assets=${JSON.stringify(assets)};
self.addEventListener('install',event=>{event.waitUntil(caches.open(cacheName).then(cache=>cache.addAll(assets)));});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(async keys=>{console.log('[开始] 旧应用缓存清理');for(const [keyIndex,key] of keys.entries()){console.log('[开始] 缓存 '+(keyIndex+1)+'/'+keys.length);console.log('[开始] 缓存版本检查');if(key.startsWith('nature-shell-')&&key!==cacheName){console.log('[分支] 清理旧外壳');await caches.delete(key);}else{console.log('[分支] 保留');}console.log('[结束] 缓存版本检查');console.log('[结束] 缓存 '+(keyIndex+1)+'/'+keys.length);}console.log('[结束] 旧应用缓存清理');await self.clients.claim();}));});
self.addEventListener('fetch',event=>{const url=new URL(event.request.url);console.log('[开始] 离线资源范围');if(event.request.method!=='GET'||url.origin!==self.location.origin||url.pathname.startsWith('/api/')||url.pathname.startsWith('/admin')){console.log('[分支] 业务请求不缓存；[结束] 离线资源范围');return;}console.log('[分支] 应用资源；[结束] 离线资源范围');console.log('[开始] 请求类型');if(event.request.mode==='navigate'){console.log('[分支] 页面加载');event.respondWith(fetch(event.request).catch(()=>caches.match('/index.html')));}else if(assets.includes(url.pathname)){console.log('[分支] 版本静态资源');event.respondWith(caches.match(event.request).then(saved=>saved||fetch(event.request)));}else{console.log('[分支] 其他资源交给浏览器');}console.log('[结束] 请求类型');});
`;
await writeFile(join(outputPath,'sw.js'),worker);
console.log(`已生成离线应用外壳，${assets.length} 个静态资源；业务API和私人媒体不进入共享缓存。`);
