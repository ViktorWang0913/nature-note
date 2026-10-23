import * as localStore from './local-store';
import { ApiError,request,upload,operationId } from './api';
import { Project,TrackPoint } from '../types/models';
const PROJECTS='nature:projectQueue',TRACKS='nature:trackQueue',UPLOADS='nature:uploadQueue';
let flushing:Promise<void>|null=null;
function read(key:string):any[]{return localStore.Get(key)||[];}
function cacheKey(id:string){return 'nature:project:'+id;}
export async function loadProject(id:string):Promise<Project>{
  const pending=read(PROJECTS).find(p=>p.id===id);if(pending)return pending;
  try{const p=await request<Project>('/projects/'+id);localStore.Set(cacheKey(id),p);return p;}
  catch(e){const cached=localStore.Get(cacheKey(id));if(e instanceof ApiError&&e.status===0&&cached)return cached;throw e;}
}
export async function queueTrackPoints(trackId:string,points:TrackPoint[]):Promise<void>{
  if(!points.length)return;const batches=read(TRACKS);for(let i=0;i<points.length;i+=500)batches.push({id:operationId(),trackId,points:points.slice(i,i+500)});localStore.Set(TRACKS,batches);
  try{await flushQueue();}catch{/*持久队列保留到下次联网*/}
}
export async function persistPhoto(tempFilePath:string,category='unclassified'):Promise<string>{
  const accountId = localStore.AccountId();
  localStore.EnsureAccount(accountId);
  const fs=wx.getFileSystemManager();const local=wx.env.USER_DATA_PATH+'/photo-'+operationId()+'.'+(tempFilePath.split('.').pop()||'jpg');
  await new Promise<void>((resolve,reject)=>fs.copyFile({srcPath:tempFilePath,destPath:local,success:()=>resolve(),fail:reject}));
  localStore.EnsureAccount(accountId);
  const q=read(UPLOADS),op=operationId();q.push({id:op,path:local,category});localStore.Set(UPLOADS,q);return op;
}
export function pendingPhotoCount():number{return read(UPLOADS).length;}
export function pendingPhotos():any[]{return read(UPLOADS);}
export async function flushQueue():Promise<void>{
  if(flushing)return flushing;
  const accountId = localStore.AccountId();
  localStore.EnsureAccount(accountId);
  flushing=(async()=>{
    for(const batch of read(TRACKS)){
      localStore.EnsureAccount(accountId);
      await request('/tracks/'+batch.trackId+'/points','POST',{points:batch.points});localStore.Set(TRACKS,read(TRACKS).filter(b=>b.id!==batch.id));
    }
    const legacyProjects=read(PROJECTS);
    console.log('[开始] 历史画布离线副本保留，共 '+legacyProjects.length+' 份');
    for(let projectIndex=0;projectIndex<legacyProjects.length;projectIndex++){
      console.log('[开始] 历史副本 '+(projectIndex+1)+'/'+legacyProjects.length);
      localStore.EnsureAccount(accountId);const project=legacyProjects[projectIndex];
      localStore.Set('nature:legacyProject:'+project.id,project);
      localStore.Set(PROJECTS,read(PROJECTS).filter(item=>item.id!==project.id));
      console.log('[结束] 历史副本 '+(projectIndex+1)+'/'+legacyProjects.length);
    }
    console.log('[结束] 历史画布离线副本保留');
    for(const item of read(UPLOADS)){
      localStore.EnsureAccount(accountId);
      const asset=await upload('/assets/upload',item.path,{operation_id:item.id,category:item.category});
      localStore.Set('nature:uploaded:'+item.id,asset);localStore.Set('nature:asset-local:'+asset.id,{path:item.path,url:asset.url});localStore.Set(UPLOADS,read(UPLOADS).filter(i=>i.id!==item.id));
    }
  })();try{await flushing;}finally{flushing=null;}
}
