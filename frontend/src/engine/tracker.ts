import * as localStore from './../services/local-store';
import { request } from '../services/api';
import { queueTrackPoints } from '../services/sync';
import { TrackPoint } from '../types/models';
import { uid } from './scene';

export interface ObservationNode {id:string;latitude:number;longitude:number;time:string;place_name?:string;text:string;asset_ids:string[];cover_asset_id?:string;project_id:string;track_id:string;remote_id?:string;dirty?:boolean;}
export interface LocalTrack {id:string;remote_id?:string;project_id:string;title:string;status:'recording'|'paused'|'ended';points:TrackPoint[];nodes:ObservationNode[];segment:number;uploaded:number;seconds:number;started_at:number|null;route_added?:boolean;interrupted?:boolean;background:boolean;}
const KEY='nature:gps:active';let active:LocalTrack|null=null,initialized=false,listening=false,syncing:Promise<void>|null=null;
let activeAccountId='';
function EnsureTrackerAccount(){
 const accountId=localStore.AccountId();console.log('[开始] 内存轨迹账号检查');
 if(activeAccountId!==accountId){console.log('[分支] 账号切换，清空内存引用并停止原监听');wx.stopLocationUpdate({fail:()=>{}});active=null;initialized=false;activeAccountId=accountId;}else{console.log('[分支] 同一账号');}console.log('[结束] 内存轨迹账号检查');
}
let listeners:((track:LocalTrack|null,error?:string)=>void)[]=[];
export function getActiveTrack():LocalTrack|null {EnsureTrackerAccount();if(!initialized){initialized=true;active=localStore.Get(KEY)||null;if(active?.status==='recording'){active.status='paused';active.started_at=null;active.segment++;active.interrupted=true;persist();}}return active;}
function persist(){localStore.EnsureAccount(activeAccountId);if(active){localStore.Set(KEY,active);localStore.Set('nature:track-local:'+active.id,active);}listeners.forEach(fn=>fn(active));}
export function subscribe(fn:(track:LocalTrack|null,error?:string)=>void):()=>void{listeners.push(fn);fn(getActiveTrack());return()=>{listeners=listeners.filter(l=>l!==fn);};}
function elapsed(){if(active?.started_at){active.seconds+=(Date.now()-active.started_at)/1000;active.started_at=Date.now();}}
function onLocation(position:any){EnsureTrackerAccount();if(!active||active.status!=='recording')return;if(!Number.isFinite(position.latitude)||!Number.isFinite(position.longitude)||position.accuracy>150)return;
  const last=active.points[active.points.length-1],now=Date.now();if(last&&last.segment===active.segment&&now-Date.parse(last.timestamp)<3000)return;
  active.points.push({sequence:active.points.length,latitude:position.latitude,longitude:position.longitude,accuracy:position.accuracy||0,timestamp:new Date(now).toISOString(),segment:active.segment});elapsed();persist();if(active.points.length-active.uploaded>=8)syncTrack().catch(()=>{});
}
async function locationPermission():Promise<boolean>{await new Promise<void>((resolve,reject)=>wx.authorize({scope:'scope.userLocation',success:()=>resolve(),fail:reject}));
  let background=false;try{await new Promise<void>((resolve,reject)=>wx.startLocationUpdateBackground({type:'gcj02',success:()=>resolve(),fail:reject}));background=true;}catch(_){await new Promise<void>((resolve,reject)=>wx.startLocationUpdate({type:'gcj02',success:()=>resolve(),fail:reject}));}return background;}
export async function startTrack(projectId:string,title:string):Promise<LocalTrack>{
  const old=getActiveTrack();if(old&&old.status!=='ended')throw new Error('已有未结束轨迹，请继续或结束当前记录');if(old?.status==='ended'){try{await syncTrack();}catch(_){throw new Error('上一条轨迹尚未完成同步，请联网后开始新记录');}}
  const background=await locationPermission();active={id:uid('local-track'),project_id:projectId,title,status:'recording',points:[],nodes:[],segment:0,uploaded:0,seconds:0,started_at:Date.now(),background};if(!listening){wx.onLocationChange(onLocation);listening=true;}wx.getLocation({type:'gcj02',success:onLocation,fail:()=>{}});persist();syncTrack().catch(()=>{});return active;
}
export async function pauseTrack():Promise<void>{if(!active||active.status!=='recording')return;elapsed();active.started_at=null;active.status='paused';active.segment++;persist();wx.stopLocationUpdate({fail:()=>{}});syncTrack().catch(()=>{});}
export async function resumeTrack():Promise<void>{if(!active||active.status!=='paused')return;active.background=await locationPermission();active.status='recording';active.started_at=Date.now();active.interrupted=false;if(!listening){wx.onLocationChange(onLocation);listening=true;}wx.getLocation({type:'gcj02',success:onLocation,fail:()=>{}});persist();syncTrack().catch(()=>{});}
export async function endTrack():Promise<LocalTrack>{if(!active)throw new Error('没有正在记录的轨迹');elapsed();active.status='ended';active.started_at=null;active.interrupted=false;persist();wx.stopLocationUpdate({fail:()=>{}});try{await syncTrack();}catch(_){}return active;}
export function localNode(id:string):ObservationNode|undefined{return getActiveTrack()?.nodes.find(n=>n.id===id||n.remote_id===id);}
export function SaveLocalNode(node:ObservationNode):ObservationNode{
  console.log('[开始] 观察点坐标有效性');
  if(!Number.isFinite(node.latitude)||!Number.isFinite(node.longitude)||Math.abs(node.latitude)>90||Math.abs(node.longitude)>180){
    console.log('[分支] 无效坐标；[结束] 观察点坐标有效性');throw new Error('请取得有效位置后再保存');
  }
  console.log('[分支] 有效坐标；[结束] 观察点坐标有效性');
  const track=getActiveTrack();
  console.log('[开始] 保存观察点所属轨迹检查');
  if(!track||track.id!==node.track_id||track.project_id!==node.project_id||track.status==='ended'){
    console.log('[分支] 轨迹已结束或已切换；[结束] 保存观察点所属轨迹检查');
    throw new Error('原轨迹已结束或已切换，请返回当前轨迹重新添加观察点');
  }
  console.log('[分支] 当前有效轨迹；[结束] 保存观察点所属轨迹检查');
  const existing=track.nodes.find(item=>item.id===node.id);
  console.log('[开始] 观察点重复保存检查');
  if(existing){
    console.log('[分支] 更新同一观察点');Object.assign(existing,node,{dirty:true});
  }else{
    console.log('[分支] 首次保存才加入轨迹');track.nodes.push({...node,dirty:true});
  }
  console.log('[结束] 观察点重复保存检查');
  persist();
  return track.nodes.find(item=>item.id===node.id)!;
}
export function updateLocalNode(id:string,changes:Partial<ObservationNode>){const n=localNode(id);if(!n)throw new Error('观察点不存在');Object.assign(n,changes,{dirty:true});persist();syncTrack().catch(()=>{});}
export function trackDuration(track:LocalTrack):number{return track.seconds+(track.started_at?(Date.now()-track.started_at)/1000:0);}
export function distance(points:TrackPoint[]):number{let m=0;for(let i=1;i<points.length;i++){const a=points[i-1],b=points[i];if(a.segment!==b.segment)continue;const r=Math.PI/180,dlat=(b.latitude-a.latitude)*r,dlon=(b.longitude-a.longitude)*r;const v=Math.sin(dlat/2)**2+Math.cos(a.latitude*r)*Math.cos(b.latitude*r)*Math.sin(dlon/2)**2;m+=6371000*2*Math.atan2(Math.sqrt(v),Math.sqrt(1-v));}return m;}
async function syncNodeEdits():Promise<void>{
  const keys=localStore.Info().keys;
  for(const key of keys.filter(k=>k.startsWith('nature:node-pending:'))){const id=key.slice('nature:node-pending:'.length),patch=localStore.Get(key);await request('/nodes/'+id,'PATCH',{place_name:patch.place_name,text:patch.text,asset_ids:patch.asset_ids,cover_asset_id:patch.cover_asset_id});localStore.Remove(key);}
  for(const key of keys.filter(k=>k.startsWith('nature:node-uploads:'))){const id=key.slice('nature:node-uploads:'.length),ops:string[]=localStore.Get(key)||[],remaining:string[]=[],ready:any[]=[];for(const op of ops){const a=localStore.Get('nature:uploaded:'+op);if(a)ready.push(a);else remaining.push(op);}if(!ready.length)continue;
    const local=localNode(id),cached:any=local||localStore.Get('nature:node:'+id);if(!cached)continue;const assetIds=Array.from(new Set<string>([...(cached.asset_ids||[]),...ready.map(a=>a.id)]));cached.asset_ids=assetIds;cached.cover_asset_id=cached.cover_asset_id||ready[0].id;for(const a of ready)localStore.Set('nature:asset:'+a.id,a);
    if(local){local.dirty=true;persist();}else if(!cached.layout_only){await request('/nodes/'+id,'PATCH',{asset_ids:assetIds,cover_asset_id:cached.cover_asset_id});}localStore.Set('nature:node:'+id,cached);localStore.Set(key,remaining);

  }
}
export async function syncTrack():Promise<void>{EnsureTrackerAccount();if(syncing)return syncing;syncing=(async()=>{await syncNodeEdits();const track=getActiveTrack();if(!track)return;
  if(!track.remote_id){const remote=await request<any>('/tracks','POST',{project_id:track.project_id,title:track.title,operation_id:track.id});track.remote_id=remote.id;persist();}
  if(track.points.length>track.uploaded){const end=track.points.length;await queueTrackPoints(track.remote_id,track.points.slice(track.uploaded,end));track.uploaded=end;persist();}
  for(const n of track.nodes){if(!n.remote_id){const remote=await request<any>('/tracks/'+track.remote_id+'/nodes','POST',{latitude:n.latitude,longitude:n.longitude,time:n.time,place_name:n.place_name,text:n.text,asset_ids:n.asset_ids,cover_asset_id:n.cover_asset_id,operation_id:n.id});n.remote_id=remote.id;n.dirty=false;persist();}else if(n.dirty){await request('/nodes/'+n.remote_id,'PATCH',{place_name:n.place_name,text:n.text,asset_ids:n.asset_ids,cover_asset_id:n.cover_asset_id});n.dirty=false;persist();}}
  await request('/tracks/'+track.remote_id,'PATCH',{status:track.status});

  persist();})();try{await syncing;}finally{syncing=null;}}
