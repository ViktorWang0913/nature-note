import { reactive } from 'vue';
import { ReadValue, WriteValue, RemoveValue, FlushStorage } from './storage';
import { StopLocation } from './platform';
export const authState=reactive({ready:false,user:null as any,mustChange:false,error:''});
export let authEpoch=0;
export class ApiError extends Error{constructor(public status:number,public code:string,message:string,public details:any=null){super(message);}}
export function ClearAccount(){window.dispatchEvent(new Event('nature-location-interrupted'));StopLocation();authEpoch++;authState.user=null;RemoveValue('nature:user');}
export async function AuthRequest(path:string,body?:any){
  const response=await fetch('/api/v1/auth/'+path,{method:body===undefined?'GET':'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Nature-Action':'web'},body:body===undefined?undefined:JSON.stringify(body)});
  const result=await response.json();console.log('[开始] 身份接口结果');
  if(!response.ok){console.log('[分支] 请求失败；[结束] 身份接口结果');throw new ApiError(response.status,result.detail?.code,result.detail?.message||'登录失败');}
  console.log('[分支] 请求成功；[结束] 身份接口结果');return result;
}
export async function RefreshSession(){
  await AuthRequest('session').then(result=>{authState.user=result.user;authState.mustChange=result.must_change;WriteValue('nature:user',result.user);RemoveValue('nature:signedOut');},error=>{
    console.log('[开始] 登录恢复失败类型');
    if(error instanceof ApiError){console.log('[分支] 需要登录');ClearAccount();}
    else{console.log('[分支] 离线读取已有账号，联网后重新校验');authState.user=ReadValue('nature:user')||null;}
    console.log('[结束] 登录恢复失败类型');
  });authState.ready=true;
}
export async function Authenticate(username:string,password:string){const result=await AuthRequest('login',{username,password});authEpoch++;authState.user=result.user;authState.mustChange=result.must_change;WriteValue('nature:user',result.user);RemoveValue('nature:signedOut');await FlushStorage();}
export async function LogoutSession(){window.dispatchEvent(new Event('nature-location-interrupted'));StopLocation();await AuthRequest('logout',{});ClearAccount();WriteValue('nature:signedOut',true);await FlushStorage();location.replace('/');}
