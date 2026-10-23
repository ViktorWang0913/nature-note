import { CurrentAccount, ReadFile, WriteFile } from './storage';
const objectUrls=new Map<string,string>();

export async function ReadBlob(source:string):Promise<Blob>{
  console.log('[开始] 图片来源读取');
  if(source.startsWith('webfile:')){
    console.log('[分支] 本账号离线图片；[结束] 图片来源读取');const blob=await ReadFile(source);
    console.log('[开始] 图片存在检查');
    if(!blob){console.log('[分支] 不存在；[结束] 图片存在检查');throw new Error('本机图片不可用，请重新选择');}
    console.log('[分支] 已读取；[结束] 图片存在检查');return blob;
  }
  console.log('[分支] 获取图片；[结束] 图片来源读取');const response=await fetch(source,{credentials:'same-origin'});
  console.log('[开始] 图片响应检查');
  if(!response.ok){console.log('[分支] 下载失败；[结束] 图片响应检查');throw new Error('图片读取失败');}
  console.log('[分支] 下载成功；[结束] 图片响应检查');return response.blob();
}
export async function MediaUrl(source:string){
  console.log('[开始] 图片路径类型');
  if(!source.startsWith('webfile:')){console.log('[分支] 浏览器地址；[结束] 图片路径类型');return source;}
  console.log('[分支] 本机图片；[结束] 图片路径类型');const key=CurrentAccount()+':'+source;
  console.log('[开始] 图片对象缓存');
  if(!objectUrls.has(key)){console.log('[分支] 创建对象地址');objectUrls.set(key,URL.createObjectURL(await ReadBlob(source)));}
  else{console.log('[分支] 复用对象地址');}console.log('[结束] 图片对象缓存');return objectUrls.get(key)!;
}
export async function CachedImage(source:string,assetId:string){
  const accountId=CurrentAccount(),key='canvas:'+assetId+':'+source.split('?')[0];let blob:Blob;
  try{blob=await ReadBlob(source);}catch(error){
    console.log('[开始] 图片离线副本检查');const saved=await ReadFile(key);
    if(!saved){console.log('[分支] 无缓存；[结束] 图片离线副本检查');throw error;}
    console.log('[分支] 使用已有副本；[结束] 图片离线副本检查');blob=saved;
  }
  console.log('[开始] 图片账号边界');
  if(accountId!==CurrentAccount()){console.log('[分支] 账号已切换；[结束] 图片账号边界');throw new Error('账号已切换');}
  console.log('[分支] 当前账号；[结束] 图片账号边界');await WriteFile(key,blob);return URL.createObjectURL(blob);
}
