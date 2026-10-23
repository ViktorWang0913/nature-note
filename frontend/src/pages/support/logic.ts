import {request} from '../../services/api';
import {pickPhoto,fail,confirm} from '../../components/flows';
import * as localStore from '../../services/local-store';

export default {
 data:{restricted:false,text:'',category:'other',categoryIndex:4,categories:['账号','AI 使用','额度','笔记与图鉴','其他'],categoryIds:['account','ai','quota','notes','other'],assets:[],items:[],announcements:[],corrections:[],busy:false,error:'',storageSize:0,pendingCount:0},
 onLoad(){this.Load();},
 async Load(){const restricted=!!localStore.Get('nature:user')?.restricted;
 console.log('[开始] 反馈权限视图');
 if(restricted){console.log('[分支] 仅显示账号申诉');this.setData({restricted,category:'account',categoryIndex:0});}
 else{console.log('[分支] 普通帮助中心');}console.log('[结束] 反馈权限视图');
 const [feedback,announcements,corrections]:any[]=await Promise.all([request('/feedback'),restricted?Promise.resolve({items:[]}):request('/announcements'),restricted?Promise.resolve({items:[]}):request('/corrections')]);const info=localStore.Info();this.setData({items:feedback.items,announcements:announcements.items,corrections:corrections.items,storageSize:info.currentSize,pendingCount:(localStore.Get('nature:uploadQueue')||[]).length+(localStore.Get('nature:projectQueue')||[]).length+(localStore.Get('nature:trackQueue')||[]).length});},
 Input(e:any){this.setData({text:e.detail.value});},
 Category(e:any){const index=Number(e.detail.value);this.setData({categoryIndex:index,category:this.data.categoryIds[index]});},
 async Image(){console.log('[开始] 反馈图片数量检查');if(this.data.assets.length>=3){console.log('[分支] 已达三张');console.log('[结束] 反馈图片数量检查；提前结束');return;}console.log('[分支] 添加截图');console.log('[结束] 反馈图片数量检查');await pickPhoto('album').then(asset=>this.setData({assets:[...this.data.assets,asset]}),fail);},
 async Submit(){console.log('[开始] 反馈输入检查');if(!this.data.text.trim()||this.data.busy){console.log('[分支] 内容为空或提交中');console.log('[结束] 反馈输入检查；提前结束');return;}console.log('[分支] 提交本人反馈');console.log('[结束] 反馈输入检查');this.setData({busy:true});await request('/feedback','POST',{category:this.data.category,text:this.data.text,asset_ids:this.data.assets.map((asset:any)=>asset.id)}).then(()=>{this.setData({text:'',assets:[]});return this.Load();},fail).finally(()=>this.setData({busy:false}));},
 async Reply(e:any){const answer:any=await new Promise(resolve=>wx.showModal({title:'补充反馈',editable:true,success:resolve}));console.log('[开始] 补充反馈确认');if(answer.confirm&&answer.content?.trim()){console.log('[分支] 提交补充');await request('/feedback/'+e.currentTarget.dataset.id+'/reply','POST',{text:answer.content.trim()});await this.Load();}else{console.log('[分支] 取消');}console.log('[结束] 补充反馈确认');},
 async Correction(e:any){await request('/corrections/'+e.currentTarget.dataset.id,'POST',{accept:e.currentTarget.dataset.accept===true}).then(()=>this.Load(),fail);},
 async ClearCache(){console.log('[开始] 清理可下载缓存确认');if(!await confirm('清理缓存','仅清理可重新下载的资源索引。未同步记录、照片、AI 输入和发布草稿保留。')){console.log('[分支] 取消');console.log('[结束] 清理可下载缓存确认；提前结束');return;}console.log('[分支] 清理已同步缓存');console.log('[结束] 清理可下载缓存确认');const keys=localStore.Info().keys.filter(key=>key.startsWith('nature:asset:'));console.log('[开始] 清理缓存索引');keys.forEach((key,index)=>{console.log(`[开始] 缓存 ${index+1}/${keys.length}`);localStore.Remove(key);console.log(`[结束] 缓存 ${index+1}/${keys.length}`);});console.log('[结束] 清理缓存索引');wx.showToast({title:'可下载缓存已清理'});await this.Load();}
};
