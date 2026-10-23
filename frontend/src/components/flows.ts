import * as localStore from './../services/local-store';
import { request, upload, errorMessage, ensureLogin, waitForTask } from '../services/api';
import { persistPhoto, flushQueue } from '../services/sync';
export const fail=(error:any)=>wx.showToast({title:errorMessage(error),icon:'none',duration:3000});
export const operation=()=>Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,9);
export function go(url:string){wx.navigateTo({url});}
export function selectTab(index:number){const pages:any[]=getCurrentPages();const current=pages[pages.length-1];if(current&&current.getTabBar)current.getTabBar()?.setData({selected:index});}
export async function pickPhoto(source:'camera'|'album'|'all'='all'):Promise<any>{
 const response:any=await new Promise((resolve,reject)=>wx.chooseMedia({count:1,mediaType:['image'],sourceType:source==='all'?['album','camera']:[source],success:resolve,fail:reject}));
 const path=response.tempFiles[0].tempFilePath;
 const op=await persistPhoto(path,'unclassified');
 try{await flushQueue();}catch{throw new Error('照片已保存在本机，联网后可在图库补传');}
 const asset=localStore.Get('nature:uploaded:'+op);
 if(!asset)throw new Error('照片已进入上传队列，请稍后在图库补传');
 return asset;
}
export async function waitTask(id:string,update?:(task:any)=>void):Promise<any>{
 return waitForTask(id,update);
}
export function confirm(title:string,content:string):Promise<boolean>{return new Promise(resolve=>wx.showModal({title,content,success:(r:any)=>resolve(r.confirm),fail:()=>resolve(false)}));}
export const query=(values:Record<string,any>)=>Object.keys(values).filter(k=>values[k]!==''&&values[k]!==undefined).map(k=>encodeURIComponent(k)+'='+encodeURIComponent(values[k])).join('&');
export function imageUrl(asset:any){return asset?.thumbnail_url||asset?.url||asset?.file_url||asset?.image_url||'';}
export function decorateAsset(asset:any){return {...asset,url:asset?.url||asset?.image_url||imageUrl(asset),label:asset.source==='photo'?'我的照片':asset.source==='generated'?'生成素材':'公共素材'};}
export function preview(url:string,urls?:string[]){if(url)wx.previewImage({current:url,urls:urls||[url]});}
