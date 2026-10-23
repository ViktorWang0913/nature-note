import * as localStore from './local-store';
import { request } from './api';
import {localNode,updateLocalNode,syncTrack} from '../engine/tracker';
import { Project } from '../types/models';
export function currentProjectId():string { return localStore.Get('nature:currentProject')||''; }
export function setCurrentProject(id:string):void { localStore.Set('nature:currentProject',id); }
export async function getCurrentProject():Promise<Project> { const id=currentProjectId()||await chooseProject();return request<Project>('/projects/'+id); }
let pendingSelection:Promise<string>|null=null;
export async function chooseProject():Promise<string> {
  console.log('[开始] 笔记选择去重');
  if(pendingSelection){console.log('[分支] 等待同一次选择；[结束] 笔记选择去重；提前返回');return pendingSelection;}
  console.log('[分支] 打开选择；[结束] 笔记选择去重');
  pendingSelection=ChooseProject();
  return pendingSelection.finally(()=>{pendingSelection=null;});
}
async function ChooseProject():Promise<string>{
  const accountId=localStore.AccountId();
  const data=await request<any>('/projects');const items=(data.items||[]).filter((project:Project)=>project.layout.designMode!=='manual');
  const current=items.find((project:any)=>project.id===currentProjectId());
  console.log('[开始] 当前笔记检查');
  if(current){console.log('[分支] 继续当前笔记；[结束] 当前笔记检查；提前返回');return current.id;}
  console.log('[分支] 选择已有笔记或明确创建；[结束] 当前笔记检查');
  const choices=items.slice(0,5);
  const choice:any=await new Promise((resolve,reject)=>wx.showActionSheet({itemList:[...choices.map((project:any)=>project.title||'未命名笔记'),'新建笔记'],success:resolve,fail:reject}));
  localStore.EnsureAccount(accountId);
  let projectId:string;
  console.log('[开始] 笔记选择结果');
  if(choice.tapIndex<choices.length){console.log('[分支] 使用已有笔记');projectId=choices[choice.tapIndex].id;}
  else{
    console.log('[分支] 先确认名称，再创建笔记');
    const answer:any=await new Promise(resolve=>wx.showModal({title:'新建观察笔记',editable:true,placeholderText:'例如：周末公园观察',confirmText:'创建',success:resolve}));
    console.log('[开始] 创建笔记确认');
    if(!answer.confirm){console.log('[分支] 取消，不创建；[结束] 创建笔记确认；[结束] 笔记选择结果；提前结束');throw new Error('已取消创建笔记');}
    console.log('[分支] 创建已确认的笔记；[结束] 创建笔记确认');
    localStore.EnsureAccount(accountId);
    const project=await request<Project>('/projects','POST',{title:answer.content?.trim()||'自然观察 '+new Date().toLocaleDateString('zh-CN')});projectId=project.id;
  }
  console.log('[结束] 笔记选择结果');setCurrentProject(projectId);return projectId;
}
export async function importAsset(assetId:string,projectId?:string):Promise<string> {
  const id=projectId||currentProjectId()||await chooseProject();
  const detail:any=await request('/projects/'+id+'/route');
  const nodes=detail.tracks.flatMap((track:any)=>track.nodes.map((node:any,index:number)=>({...node,label:track.title+' · '+(node.place_name||'观察点 '+(index+1))})));
  console.log('[开始] 素材观察点选择');
  if(!nodes.length){console.log('[分支] 当前笔记还没有观察点');console.log('[结束] 素材观察点选择；提前结束');throw new Error('请先在该笔记中记录 GPS 并添加观察点');}
  console.log('[分支] 选择素材归属的具体观察点');console.log('[结束] 素材观察点选择');
  const selected=await ChooseObservation(nodes);
  const node:any=await request('/nodes/'+selected.id);
  const patch={asset_ids:Array.from(new Set([...(node.asset_ids||[]),assetId])),cover_asset_id:node.cover_asset_id||assetId};
  console.log('[开始] 本机观察点同步');
  if(localNode(node.id)){console.log('[分支] 更新本机记录后同步');updateLocalNode(node.id,patch);await syncTrack();}
  else{console.log('[分支] 更新云端观察点');await request('/nodes/'+node.id,'PATCH',patch);}
  console.log('[结束] 本机观察点同步');setCurrentProject(id);return id;
}

async function ChooseObservation(nodes:any[],offset=0):Promise<any>{
  const page=nodes.slice(offset,offset+5),labels=page.map((node:any)=>node.label.slice(0,30));
  console.log('[开始] 观察点选择分页');
  if(nodes.length>5){console.log('[分支] 追加翻页入口');labels.push(offset+5<nodes.length?'更多观察点 →':'返回第一页 ↺');}
  else{console.log('[分支] 本页显示全部观察点');}
  console.log('[结束] 观察点选择分页');
  const choice:any=await new Promise((resolve,reject)=>wx.showActionSheet({itemList:labels,success:resolve,fail:reject}));
  console.log('[开始] 观察点选择结果');
  if(choice.tapIndex<page.length){console.log('[分支] 已选择观察点');console.log('[结束] 观察点选择结果；提前返回');return page[choice.tapIndex];}
  console.log('[分支] 切换列表页');console.log('[结束] 观察点选择结果');
  return ChooseObservation(nodes,(offset+5<nodes.length?offset+5:0));
}
