import {workspace} from '../../services/workspace';
import {request, waitForTask} from '../../services/api';
import {pickPhoto, fail, confirm} from '../../components/flows';
import * as localStore from '../../services/local-store';

export default {
 behaviors:[workspace],
 onResize(event:any){this.ResizeWindow(event);},
 KeyboardChanged(event:any){this.ApplyKeyboardHeight(event);},
 _accountId:'',_watchEpoch:0,_watching:'',_visible:true,_loadEpoch:0,_blankSession:false,
 data:{deletingId:'',historyNext:'',sessions:[],sessionId:'',title:'问问自然记',messages:[],text:'',asset:null,answer:'',taskId:'',busy:false,error:'',phase:'',context:{percent:0,used:0,limit:16000,reserved_output:2000,estimated:true},quota:[],quotaPercent:0,showHistory:false,keyboardHeight:0,scrollTop:0},
 onLoad(options:any){this.MeasureWindow();this.setData({text:options.species?decodeURIComponent(options.species)+'：':''});this.Load().then(undefined,fail);},
 onShow(){this.MeasureWindow();this._visible=true;console.log('[开始] 问答页面恢复');if(this.data.sessionId){console.log('[分支] 读取后台继续的任务');this.Load().then(undefined,fail);}else{console.log('[分支] 等待首次初始化');}console.log('[结束] 问答页面恢复');},
 onHide(){this._visible=false;++this._watchEpoch;this._watching='';this.setData({keyboardHeight:0});this.SaveDraft();},
 onUnload(){this._visible=false;++this._watchEpoch;this.SaveDraft();},
 async Load(){
  const loadEpoch=++this._loadEpoch;
  const result:any=await request('/chats');
  console.log('[开始] 历史加载有效性');
  if(loadEpoch!==this._loadEpoch){console.log('[分支] 忽略删除或切换前的列表');console.log('[结束] 历史加载有效性；提前结束');return;}
  console.log('[分支] 当前列表');console.log('[结束] 历史加载有效性');
  this._accountId=localStore.AccountId();this.setData({sessions:result.items,historyNext:result.next_cursor||''});
  console.log('[开始] 对话初始化选择');
  if(!this.data.sessionId){
   console.log('[分支] 选择最近会话或新建');
   console.log('[开始] 历史会话检查');
   if(result.items.length&&!this._blankSession){console.log('[分支] 最近会话');this.setData({sessionId:result.items[0].id});}
   else{console.log('[分支] 保留空白，发送时再建立会话');}
   console.log('[结束] 历史会话检查');
  }else{console.log('[分支] 使用已选择会话');}
  console.log('[结束] 对话初始化选择');
  console.log('[开始] 空白对话检查');
  if(!this.data.sessionId){console.log('[分支] 只更新额度');const quota:any=await request('/me/quota');console.log('[开始] 空白额度响应检查');if(loadEpoch===this._loadEpoch){console.log('[分支] 更新当前空白页');this.setData({quota:quota.items,quotaPercent:quota.items.find((item:any)=>item.provider==='qwen')?.remaining_percent??0});}else{console.log('[分支] 忽略旧响应');}console.log('[结束] 空白额度响应检查');console.log('[结束] 空白对话检查；提前结束');return;}
  console.log('[分支] 读取已保存会话');console.log('[结束] 空白对话检查');
  const sessionId=this.data.sessionId;
  const detail:any=await request('/chats/'+sessionId);const quota:any=await request('/me/quota');
  const draft=localStore.Get('nature:chat-draft:'+this.data.sessionId)||{};
  console.log('[开始] 问答加载会话一致检查');
  if(loadEpoch!==this._loadEpoch||sessionId!==this.data.sessionId||!this._visible){console.log('[分支] 忽略离开页面或已切换会话的响应');console.log('[结束] 问答加载会话一致检查；提前退出');return;}
  console.log('[分支] 当前会话');console.log('[结束] 问答加载会话一致检查');
  this.setData({title:detail.title,messages:detail.messages,context:detail.context,quota:quota.items,quotaPercent:quota.items.find((item:any)=>item.provider==='qwen')?.remaining_percent??0,text:this.data.text||draft.text||'',asset:this.data.asset||draft.asset||null,scrollTop:this.data.scrollTop+100000});
  const lastMessage=detail.messages[detail.messages.length-1];
  console.log('[开始] 恢复问答任务检查');
  if(lastMessage?.task_id){
   console.log('[分支] 查询最近任务');const task:any=await request('/tasks/'+lastMessage.task_id);
   console.log('[开始] 恢复任务会话边界检查');
   if(sessionId!==this.data.sessionId||!this._visible){console.log('[分支] 已切换会话或离开页面');console.log('[结束] 恢复任务会话边界检查；提前结束');console.log('[结束] 恢复问答任务检查；提前结束');return;}
   console.log('[分支] 当前会话');console.log('[结束] 恢复任务会话边界检查');
   console.log('[开始] 最近任务状态');if(task.status==='queued'||task.status==='running'){console.log('[分支] 继续等待后台任务');this.Watch(task.id,sessionId);}else{console.log('[分支] 已结束');this.setData({busy:false});}console.log('[结束] 最近任务状态');
  }
  else{console.log('[分支] 尚无任务');this.setData({busy:false});}
  console.log('[结束] 恢复问答任务检查');
 },
 SaveDraft(){console.log('[开始] 草稿账号检查');if(this._accountId!==localStore.AccountId()){console.log('[分支] 账号已改变，拒绝旧页面写入');console.log('[结束] 草稿账号检查；提前结束');return;}console.log('[分支] 当前账号草稿');console.log('[结束] 草稿账号检查');localStore.Set('nature:chat-draft:'+this.data.sessionId,{text:this.data.text,asset:this.data.asset});},
 Input(e:any){this.setData({text:e.detail.value});this.SaveDraft();},
 async Estimate(){console.log('[开始] 上下文会话检查');if(!this.data.sessionId){console.log('[分支] 尚未开始对话');console.log('[结束] 上下文会话检查；提前结束');return;}console.log('[分支] 读取上下文');console.log('[结束] 上下文会话检查');const sessionId=this.data.sessionId;const result:any=await request('/chats/'+sessionId+'/context','POST',{text:this.data.text,asset_id:(this.data.asset as any)?.id||null});console.log('[开始] 上下文返回检查');if(sessionId===this.data.sessionId){console.log('[分支] 更新当前对话');this.setData({context:result});}else{console.log('[分支] 忽略旧对话');}console.log('[结束] 上下文返回检查');},
 async ContextDetails(){await this.Estimate();const context=this.data.context;wx.showModal({title:'对话上下文',content:`预计已用 ${context.used}，预留回答 ${context.reserved_output}，上限 ${context.limit}。上下文用于理解本次聊天，与每日额度不同。达到上限会自动整理早期对话，原记录保留。`,showCancel:false});},
 async ChooseImage(source:'camera'|'album'|'all'='all'){await pickPhoto(source).then(asset=>{this.setData({asset});this.SaveDraft();this.Estimate();},fail);},
 Preview(event:any){wx.previewImage({current:event.currentTarget.dataset.url,urls:[event.currentTarget.dataset.url]});},
 History(){this.setData({showHistory:true});this.Load().then(undefined,fail);},
 MoreHistory(){request('/chats?cursor='+encodeURIComponent(this.data.historyNext)).then((result:any)=>this.setData({sessions:[...this.data.sessions,...result.items],historyNext:result.next_cursor||''}),fail);},
 DeleteHistory(event:any){this.Delete(event.currentTarget.dataset.id).then(undefined,fail);},
 CloseHistory(){this.setData({showHistory:false});},
 Noop(){},
 SessionMenu(){
  const actions=[{title:'新对话',run:()=>this.New(),disabled:this.data.busy},{title:'重命名',run:()=>this.Rename(),disabled:!this.data.sessionId},{title:'查看额度',run:()=>this.QuotaDetails(),disabled:false},{title:'用当前输入创作图片',run:()=>this.ToImage({currentTarget:{dataset:{}}}),disabled:false},{title:'删除对话',run:()=>this.Delete(),disabled:this.data.busy||!this.data.sessionId}].filter(action=>!action.disabled);
  wx.showActionSheet({itemList:actions.map(action=>action.title),success:choice=>{console.log('[开始] 对话菜单 '+actions[choice.tapIndex].title);Promise.resolve(actions[choice.tapIndex].run()).then(()=>console.log('[结束] 对话菜单'),fail);}});
 },
 ImageMenu(){wx.showActionSheet({itemList:['拍照','从手机相册选择','从我的照片选择'],success:choice=>{const actions=[()=>this.ChooseImage('camera'),()=>this.ChooseImage('album'),()=>this.ExistingImage()];console.log('[开始] 图片来源选择');actions[choice.tapIndex]().then(()=>console.log('[结束] 图片来源选择'),fail);}});},
 MessageMenu(event:any){
  const message:any=this.data.messages.find((item:any)=>item.id===event.currentTarget.dataset.id);
  const actions=[{title:'引用到输入框',run:()=>this.Reference(event)},{title:'用这段文字创作图片',run:()=>this.ToImage({currentTarget:{dataset:{text:message.text}}})}];
  wx.showActionSheet({itemList:actions.map(action=>action.title),success:choice=>{console.log('[开始] 消息菜单');Promise.resolve(actions[choice.tapIndex].run()).then(()=>console.log('[结束] 消息菜单'),fail);}});
 },
 QuotaDetails(){wx.showModal({title:'问答额度',content:'识别与问答剩余 '+this.data.quotaPercent+'%。正在处理的请求可能暂时占用部分额度，完成后按实际用量更新。上下文使用量不等于每日额度。',showCancel:false});},
 RemoveImage(){this.setData({asset:null});this.SaveDraft();this.Estimate();},
 async Send(){
  console.log('[开始] 图文发送检查');
  if(this.data.busy||(!this.data.text.trim()&&!this.data.asset)){console.log('[分支] 处理中或输入为空');console.log('[结束] 图文发送检查；提前结束');return;}
  console.log('[分支] 提交用户确认的图文');console.log('[结束] 图文发送检查');
  const draftSessionId=this.data.sessionId,sentText=this.data.text,sentAsset=this.data.asset as any;
  ++this._loadEpoch;
  this.SaveDraft();this.setData({busy:true,error:'',answer:'',taskId:'',phase:'正在提交'});
  console.log('[开始] 发送会话建立');
  if(!this.data.sessionId){console.log('[分支] 首次发送创建对话');const session:any=await request('/chats','POST',{title:sentText.trim().slice(0,24)||'照片观察'}).catch(error=>{this.setData({busy:false});throw error;});this._blankSession=false;this.setData({sessionId:session.id,title:session.title,sessions:[session,...this.data.sessions]});}else{console.log('[分支] 使用当前对话');}
  console.log('[结束] 发送会话建立');
  const sessionId=this.data.sessionId;
  await request<any>('/tasks','POST',{kind:'rag',input:{chat_session_id:sessionId,question:sentText,asset_id:sentAsset?.id}}).then(async task=>{
   localStore.Remove('nature:chat-draft:'+draftSessionId);
   localStore.Remove('nature:chat-draft:'+sessionId);
   console.log('[开始] 问答提交页面检查');if(sessionId!==this.data.sessionId||!this._visible){console.log('[分支] 已切换页面，任务继续在后台');console.log('[结束] 问答提交页面检查；提前结束');return;}console.log('[分支] 更新当前页面');console.log('[结束] 问答提交页面检查');
   this.setData({taskId:task.id,messages:[...this.data.messages,{id:'pending-'+task.id,role:'user',text:sentText,asset_url:sentAsset?.url||''}],text:'',asset:null,scrollTop:this.data.scrollTop+100000});
   this.Watch(task.id,this.data.sessionId);

  },error=>{this.setData({busy:false,error:error.message});fail(error);}).then(undefined,error=>{this.setData({error:error.message});this.Load();});
 },
 Watch(taskId:string,sessionId:string){
  console.log('[开始] 任务观察器重复检查');if(this._watching===taskId){console.log('[分支] 已在等待');console.log('[结束] 任务观察器重复检查；提前结束');return;}console.log('[分支] 开始等待');console.log('[结束] 任务观察器重复检查');
  const epoch=++this._watchEpoch;this._watching=taskId;this.setData({busy:true,taskId});
  const IsCurrent=()=>this._visible&&epoch===this._watchEpoch&&sessionId===this.data.sessionId;
  waitForTask(taskId,(current:any)=>{console.log('[开始] 流式页面边界检查');if(IsCurrent()){console.log('[分支] 更新当前会话');this.setData({answer:current.result?.answer||'',phase:current.result?.phase==='compressing'?'正在整理较早的对话':current.status==='queued'?'排队中，前方 '+(current.queue_ahead||0)+' 个任务':'正在回答',context:current.result?.context||this.data.context,scrollTop:this.data.scrollTop+100000});}else{console.log('[分支] 页面已离开，停止本机等待');throw new Error('已停止本机等待，任务继续保存在后台');}console.log('[结束] 流式页面边界检查');})
   .then(()=>this.FinishWatch(epoch,sessionId,''),error=>this.FinishWatch(epoch,sessionId,error.message));
 },
 FinishWatch(epoch:number,sessionId:string,error:string){console.log('[开始] 问答观察器结束检查');if(this._visible&&epoch===this._watchEpoch&&sessionId===this.data.sessionId){console.log('[分支] 刷新当前会话');this._watching='';this.setData({busy:false,answer:'',phase:'',error});this.Load().then(undefined,fail);}else{console.log('[分支] 后台状态保留，不更新其他页面');}console.log('[结束] 问答观察器结束检查');},
 async Reference(e:any){const message:any=this.data.messages.find((item:any)=>item.id===e.currentTarget.dataset.id);this.setData({text:'引用此前内容：\n'+message.text+'\n\n'+this.data.text});this.SaveDraft();await this.Estimate();},
 async ExistingImage(){const result:any=await request('/assets?source=photo&limit=6');console.log('[开始] 已有照片检查');if(!result.items.length){console.log('[分支] 无照片');wx.showToast({title:'请先上传照片',icon:'none'});console.log('[结束] 已有照片检查；提前结束');return;}console.log('[分支] 选择照片');console.log('[结束] 已有照片检查');const choice:any=await new Promise((resolve,reject)=>wx.showActionSheet({itemList:result.items.map((item:any)=>item.title),success:resolve,fail:reject}));this.setData({asset:result.items[choice.tapIndex]});this.SaveDraft();await this.Estimate();},
 async Stop(){await request('/tasks/'+this.data.taskId+'/cancel','POST').then(()=>{this.setData({busy:false,phase:'已停止'});this.Load();},fail);},
 async New(){this.SaveDraft();this._blankSession=true;++this._loadEpoch;++this._watchEpoch;this._watching='';this.setData({sessionId:'',title:'新对话',messages:[],text:'',asset:null,answer:'',taskId:'',busy:false,error:'',phase:'',showHistory:false,context:{percent:0,used:0,limit:this.data.context.limit,reserved_output:this.data.context.reserved_output,estimated:true}});},
 async Open(e:any){this.SaveDraft();this._blankSession=false;++this._watchEpoch;this._watching='';this.setData({sessionId:e.currentTarget.dataset.id,text:'',asset:null,answer:'',busy:false,error:'',showHistory:false});await this.Load();},
 async Rename(){const answer:any=await new Promise(resolve=>wx.showModal({title:'会话名称',editable:true,placeholderText:this.data.title,success:resolve}));console.log('[开始] 重命名确认');if(answer.confirm&&answer.content?.trim()){console.log('[分支] 保存名称');await request('/chats/'+this.data.sessionId,'PATCH',{title:answer.content.trim()});await this.Load();}else{console.log('[分支] 取消');}console.log('[结束] 重命名确认');},
 async Delete(sessionId:string=this.data.sessionId){
  console.log('[开始] 删除会话确认');
  if(!sessionId||this.data.deletingId||!await confirm('删除此对话','对话将从你的历史中移除，已另存的内容保留。删除内容按隐私政策保留于管理后台。')){console.log('[分支] 取消或正在删除');console.log('[结束] 删除会话确认；提前结束');return;}
  console.log('[分支] 删除选中会话');console.log('[结束] 删除会话确认');
  this.setData({deletingId:sessionId});++this._loadEpoch;
  await request('/chats/'+sessionId,'DELETE').then(()=>{
   ++this._loadEpoch;localStore.Remove('nature:chat-draft:'+sessionId);this.setData({sessions:this.data.sessions.filter((item:any)=>item.id!==sessionId),deletingId:''});
   console.log('[开始] 删除当前对话检查');
   if(this.data.sessionId===sessionId){console.log('[分支] 清空已删除对话');this._blankSession=true;++this._watchEpoch;this._watching='';this.setData({sessionId:'',title:'新对话',messages:[],text:'',asset:null,answer:'',taskId:'',busy:false,error:'',phase:'',context:{...this.data.context,percent:0,used:0}});}else{console.log('[分支] 保留正在查看的其他对话');}
   console.log('[结束] 删除当前对话检查');wx.showToast({title:'已删除'});
  },error=>{this.setData({deletingId:''});throw error;});
 },
 ToImage(e:any){const text=e.currentTarget.dataset.text||this.data.text;localStore.Set('aiPrompt',text);localStore.Set('aiAsset',this.data.asset||null);localStore.Set('galleryTab','ai');wx.switchTab({url:'/pages/gallery/index'});}
};
