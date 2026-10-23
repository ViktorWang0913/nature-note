import * as localStore from '../../services/local-store';
import {config} from '../../services/config';
import {request,logout} from '../../services/api';
import {fail,go,confirm} from '../../components/flows';
export default {
 data:{phone:{bound:false,available:false,masked_number:''},quota:[],loading:true,error:'',user:null,nickname:'',achievements:[],section:'profile',saving:false},
 onLoad(options:any){this.setData({section:options.section||'profile'});this.load();},
 async load(){this.setData({loading:true,error:''});try{const [u,a]:any[]=await Promise.all([request('/me'),request('/me/achievements')]);const quota:any=await request('/me/quota');const phone:any=await request('/me/phone');this.setData({user:u,nickname:u.nickname,achievements:a.items||a,quota:quota.items,phone});}catch(e){this.setData({error:(e as Error).message});}finally{this.setData({loading:false});}},
 input(e:any){this.setData({nickname:e.detail.value});},
 async save(){if(!this.data.nickname.trim())return;this.setData({saving:true});try{const u:any=await request('/me','PATCH',{nickname:this.data.nickname.trim()});this.setData({user:u});wx.showToast({title:'资料已保存'});}catch(e){fail(e);}finally{this.setData({saving:false});}},
 async BindPhone(e:any){console.log('[开始] 手机号授权结果');if(!e.detail.code){console.log('[分支] 未授权，不提交绑定');console.log('[结束] 手机号授权结果；提前结束');return;}console.log('[分支] 将一次性凭据交给后端验证');console.log('[结束] 手机号授权结果');await request('/me/phone','POST',{code:e.detail.code}).then((phone:any)=>{this.setData({phone:{...this.data.phone,...phone}});wx.showToast({title:'手机号已绑定'});},fail);},
 Chat(){go('/pages/chat/index');},Support(){go('/pages/support/index');},
 async CloseAccount(){
 console.log('[开始] 注销确认');
 if(!await confirm('注销账号','确认后立即停用，公开内容下架，个人数据开始清理。必要管理记录按保留依据和期限处理，重新注册不会恢复旧资料。')){console.log('[分支] 取消');console.log('[结束] 注销确认；提前结束');return;}
 console.log('[分支] 重新验证身份');console.log('[结束] 注销确认');
 const answer:any=await new Promise(resolve=>wx.showModal({title:'输入当前密码以注销',editable:true,inputType:'password',success:resolve} as any));
 console.log('[开始] 注销密码输入');
 if(!answer.confirm){console.log('[分支] 取消；[结束] 注销密码输入');return;}
 console.log('[分支] 提交密码；[结束] 注销密码输入');
 await request('/me/close','POST',{password:answer.content,confirmation:'注销账号'}).then(()=>{location.replace('/');},fail);
 },
 ChangePassword(){window.dispatchEvent(new Event('nature-change-password'));},
 projects(){go('/pages/projects/index');},posts(){go('/pages/user/index?id='+(this.data.user as any)?.id);},
 toggle(){this.setData({section:this.data.section==='achievements'?'profile':'achievements'});},
 async logout(){if(!await confirm('退出当前账号','本地未同步记录会保留在当前设备，请先完成同步。'))return;await logout();}
};
