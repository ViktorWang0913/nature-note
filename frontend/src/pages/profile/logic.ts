import {request,logout,errorMessage} from '../../services/api';
import {fail,go,confirm,selectTab} from '../../components/flows';
export default {
 data:{phone:{bound:false,available:false,masked_number:''},quota:[],loading:true,error:'',user:null,nickname:'',achievements:[],section:'profile',saving:false,editingName:false,nameError:''},
 onLoad(options:any){this.setData({section:options.section==='achievements'?'achievements':'profile'});this.load();},
 onShow(){selectTab(3);},
 onTabItemTap(){this.setData({section:'profile'});window.scrollTo(0,0);},
 async load(){
  this.setData({loading:true,error:''});
  try{const [user,achievements,quota,phone]=await Promise.all([request('/me'),request('/me/achievements'),request('/me/quota'),request('/me/phone')]);this.setData({user,nickname:user.nickname,achievements:achievements.items||achievements,quota:quota.items,phone});}
  catch(error){this.setData({error:errorMessage(error)});}
  finally{this.setData({loading:false});}
 },
 EditName(){if(!this.data.loading&&!this.data.saving)this.setData({editingName:true,nameError:''});},
 CancelName(){if(!this.data.saving)this.setData({editingName:false,nickname:this.data.user?.nickname||'',nameError:''});},
 input(event:any){this.setData({nickname:event.detail.value,nameError:''});},
 async save(){
  if(this.data.saving)return;
  const nickname=this.data.nickname.trim();
  if(!nickname||nickname.length>24){this.setData({nameError:'请输入 1–24 个字的昵称'});return;}
  if(nickname===this.data.user?.nickname){this.setData({editingName:false});return;}
  this.setData({saving:true,nameError:''});
  try{const user=await request('/me','PATCH',{nickname});this.setData({user,nickname:user.nickname,editingName:false});wx.showToast({title:'昵称已更新'});}
  catch(error){this.setData({nameError:errorMessage(error)});}
  finally{this.setData({saving:false});}
 },
 async BindPhone(e:any){console.log('[开始] 手机号授权结果');if(!e.detail.code){console.log('[分支] 未授权，不提交绑定');console.log('[结束] 手机号授权结果；提前结束');return;}console.log('[分支] 将一次性凭据交给后端验证');console.log('[结束] 手机号授权结果');await request('/me/phone','POST',{code:e.detail.code}).then((phone:any)=>{this.setData({phone:{...this.data.phone,...phone}});wx.showToast({title:'手机号已绑定'});},fail);},
 Support(){go('/pages/support/index');},
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
 Observations(){go('/pages/observations/index');},Tutorial(){go('/pages/tutorial/index');},projects(){go('/pages/projects/index');},
 toggle(){this.setData({section:this.data.section==='achievements'?'profile':'achievements'});window.scrollTo(0,0);},
 async logout(){if(!await confirm('退出当前账号','本地未同步记录会保留在当前设备，请先完成同步。'))return;await logout();}
};
