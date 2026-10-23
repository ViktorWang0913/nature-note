import * as localStore from './local-store';
import { ApiError, authState, authEpoch, LogoutSession, ClearAccount } from '../web/auth';
import { ReadBlob } from '../web/media';
import { FlushStorage } from '../web/storage';
import { Task } from '../types/models';
export { ApiError };
export const apiBase='/api/v1';
export function errorMessage(error:any):string{return error?.message||error?.errMsg||'操作失败，请重试';}
export function showError(error:any){wx.showToast({title:errorMessage(error),icon:'none'});}
export function operationId(){return crypto.randomUUID();}
export async function ensureLogin(explicit=false,createNew=false):Promise<any>{
  console.log('[开始] 当前账号检查');
  if(!authState.user){console.log('[分支] 未登录；[结束] 当前账号检查');throw new ApiError(401,'signed_out','请先登录');}
  console.log('[分支] 使用分配账号；[结束] 当前账号检查');return authState.user;
}
export async function request<T=any>(path:string,method='GET',data?:any):Promise<T>{
  const accountId=localStore.AccountId(),epoch=authEpoch;await ensureLogin();localStore.EnsureAccount(accountId);
  const response=await fetch(apiBase+path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json','X-Nature-Action':'web'},body:data===undefined?undefined:JSON.stringify(data),signal:AbortSignal.timeout(30000)}).then(response=>response,error=>{throw new ApiError(0,'network_error','网络不可用，未同步内容仍保留在本机',error);});
  const result=await response.json();console.log('[开始] 请求账号边界');
  if(accountId!==localStore.AccountId()||epoch!==authEpoch){console.log('[分支] 拒绝旧响应；[结束] 请求账号边界');throw new ApiError(409,'account_changed','账号已切换');}
  console.log('[分支] 当前账号；[结束] 请求账号边界');console.log('[开始] 接口响应');
  if(!response.ok){
    console.log('[分支] 接口错误');console.log('[开始] 身份失效同步');
    if(response.status===401){console.log('[分支] 返回登录');ClearAccount();}
    else if(result.detail?.code==='account_disabled'){console.log('[分支] 进入申诉权限');authState.user={...authState.user,restricted:true};localStore.Set('nature:user',authState.user);location.hash='/pages/support/index';}
    else{console.log('[分支] 业务错误');}
    console.log('[结束] 身份失效同步；[结束] 接口响应');throw new ApiError(response.status,result.detail?.code||'request_failed',result.detail?.message||'请求未完成',result.detail);
  }
  console.log('[分支] 接口成功；[结束] 接口响应');return result;
}
export async function upload<T=any>(path:string,filePath:string,formData:Record<string,any>={}):Promise<T>{
  const accountId=localStore.AccountId(),epoch=authEpoch;await ensureLogin();localStore.EnsureAccount(accountId);await FlushStorage();localStore.EnsureAccount(accountId);
  const body=new FormData();body.append('file',await ReadBlob(filePath),'photo.png');
  localStore.EnsureAccount(accountId);
  console.log('[开始] 上传参数');Object.entries(formData).forEach(([key,value],index)=>{console.log(`[开始] 参数 ${index+1}/${Object.keys(formData).length}`);body.append(key,String(value));console.log(`[结束] 参数 ${index+1}/${Object.keys(formData).length}`);});console.log('[结束] 上传参数');
  const response=await fetch(apiBase+path,{method:'POST',credentials:'same-origin',headers:{'X-Nature-Action':'web'},body,signal:AbortSignal.timeout(120000)}).then(response=>response,error=>{throw new ApiError(0,'upload_failed','上传未完成，照片仍保存在本机',error);});const result=await response.json();console.log('[开始] 上传结果检查');
  if(accountId!==localStore.AccountId()||epoch!==authEpoch){console.log('[分支] 旧账号结果；[结束] 上传结果检查');throw new ApiError(409,'account_changed','账号已切换');}
  else if(!response.ok){console.log('[分支] 上传失败；[结束] 上传结果检查');throw new ApiError(response.status,result.detail?.code,result.detail?.message||'上传失败');}
  console.log('[分支] 上传成功；[结束] 上传结果检查');return result;
}
export async function waitForTask(id:string,onUpdate?:(task:Task)=>void):Promise<Task>{
  let readFailures=0;
  console.log('[开始] 任务查询，最多450次');
  for(let attemptIndex=0;attemptIndex<450;attemptIndex++){
    console.log(`[开始] 查询 ${attemptIndex+1}/450`);
    let task:Task;
    try{task=await request<Task>('/tasks/'+id);}catch(readError){
      console.log('[开始] 查询失败分类');
      if(readError instanceof ApiError&&readError.status===0&&readFailures<3){
        console.log('[分支] 网络短暂中断，只重查原任务');readFailures++;
        console.log(`[结束] 查询失败分类；[结束] 查询 ${attemptIndex+1}/450；跳过本次读取`);
        await new Promise(resolve=>setTimeout(resolve,2000));continue;
      }
      console.log('[分支] 读取失败，保留任务编号；[结束] 查询失败分类；提前结束任务查询');throw readError;
    }
    readFailures=0;onUpdate?.(task);console.log('[开始] 任务状态');
    if(task.status==='succeeded'){console.log('[分支] 已完成；[结束] 任务状态');console.log(`[结束] 查询 ${attemptIndex+1}/450；提前结束任务查询`);return task;}
    else if(task.status==='failed'||task.status==='cancelled'){console.log('[分支] 任务失败；[结束] 任务状态');throw new ApiError(422,task.status,typeof task.error==='string'?task.error:task.error?.['message']||'任务未完成');}
    console.log('[分支] 等待结果；[结束] 任务状态');console.log(`[结束] 查询 ${attemptIndex+1}/450`);await new Promise(resolve=>setTimeout(resolve,2000));
  }
  console.log('[结束] 任务查询');throw new ApiError(408,'task_pending','任务仍在处理，可稍后查看');
}
export function logout(){return LogoutSession();}
export function RegisterAgain():Promise<any>{return Promise.reject(new ApiError(403,'registration_closed','请联系管理员分配账号'));}
