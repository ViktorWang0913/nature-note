import {workspace} from '../../services/workspace';
import {DeleteMaterial} from '../../services/materials';
import * as localStore from './../../services/local-store';
import {request} from '../../services/api';
import {pendingPhotos,flushQueue} from '../../services/sync';
import {currentProjectId,getCurrentProject,chooseProject,importAsset} from '../../services/projects';
import {fail,go,pickPhoto,selectTab,decorateAsset,query,waitTask,preview,operation} from '../../components/flows';
export default {
 behaviors:[workspace],
 onResize(event:any){this.ResizeWindow(event);},
 KeyboardChanged(event:any){this.ApplyKeyboardHeight(event);},
 _blankSession:false,_libraryEpoch:0,
 _lastGenerationInput:null as any,_generationEpoch:0,_accountId:'',
 data:{removingAssetId:'',deletingId:'',historyNext:'',resultHasMessage:false,scrollTop:0,keyboardHeight:0,showHistory:false,showFilters:false,showPhotos:false,referencePhotos:[] as any[],imageQuota:100,sessions:[],sessionTitle:'图片创作',atlasTarget:null,selectedIds:[],unfiled:false,tab:'templates',loading:false,error:'',q:'',category:'all',source:'all',categories:[{id:'all',name:'全部'},{id:'unclassified',name:'未分类'},{id:'mammals',name:'兽类'},{id:'birds',name:'鸟类'},{id:'insects',name:'昆虫'},{id:'plants',name:'植物'},{id:'environment',name:'环境'},{id:'buildings',name:'建筑'}],sources:[{id:'all',name:'全部'},{id:'public',name:'公共素材'},{id:'photo',name:'我的照片'},{id:'generated',name:'生成素材'}],items:[],pending:[],syncing:false,next:'',projectTitle:'选择笔记',prompt:'',styles:[{id:'cartoon',name:'卡通插画'},{id:'watercolor',name:'水彩'},{id:'sketch',name:'素描'}],style:'cartoon',styleName:'卡通插画',inputAsset:null,result:null,task:null,busy:false,messages:[],sessionId:''},
 onShow(){this.MeasureWindow();this.CheckAccount();selectTab(1);const target=localStore.Get('atlasTarget');this.setData({atlasTarget:target||null,source:target?'photo':this.data.source});const chatPrompt=localStore.Get('aiPrompt');console.log('[开始] 问答生图输入检查');if(chatPrompt){console.log('[分支] 带入问答文字');this.setData({prompt:chatPrompt,tab:'ai'});localStore.Remove('aiPrompt');}else{console.log('[分支] 普通生图入口');}console.log('[结束] 问答生图输入检查');this.setData({pending:pendingPhotos()});const tab=localStore.Get('galleryTab');if(tab){this.setData({tab});localStore.Remove('galleryTab');}const asset=localStore.Get('aiAsset');if(asset){this.setData({inputAsset:decorateAsset(asset),tab:'ai'});localStore.Remove('aiAsset');}this.UpdateWorkspace();this.Load();},
 onReady(){this.UpdateWorkspace();},
 onHide(){this.SaveCreationDraft();this.setData({keyboardHeight:0});const tabBar=this.getTabBar?.();tabBar?.setData({hidden:false});},
 SaveCreationDraft(){console.log('[开始] 创作草稿账号检查');if(this._accountId!==localStore.AccountId()){console.log('[分支] 账号已切换，不写入旧草稿');console.log('[结束] 创作草稿账号检查；提前结束');return;}console.log('[分支] 保存当前草稿');localStore.Set('nature:image-draft:'+this.data.sessionId,{prompt:this.data.prompt,inputAsset:this.data.inputAsset,style:this.data.style,styleName:this.data.styleName});console.log('[结束] 创作草稿账号检查');},
 RestoreCreationDraft(){const draft=localStore.Get('nature:image-draft:'+this.data.sessionId);console.log('[开始] 创作草稿恢复');if(draft&&!this.data.prompt&&!this.data.inputAsset){console.log('[分支] 恢复未发送内容');this.setData(draft);}else{console.log('[分支] 保留当前输入或外部带入内容');}console.log('[结束] 创作草稿恢复');},
 CheckAccount(){const accountId=localStore.AccountId();console.log('[开始] 创作页面账号检查');if(this._accountId&&this._accountId!==accountId){console.log('[分支] 清除旧账号页面状态');++this._generationEpoch;this._lastGenerationInput=null;this.setData({sessionId:'',sessions:[],messages:[],inputAsset:null,prompt:'',result:null,task:null,busy:false,showHistory:false,showPhotos:false});}else{console.log('[分支] 当前账号页面');}this._accountId=accountId;console.log('[结束] 创作页面账号检查');},
 UpdateWorkspace(){const tabBar=this.getTabBar?.();tabBar?.setData({hidden:this.data.tab==='ai'});},
 BackToGallery(){this.setData({tab:'assets',keyboardHeight:0});this.UpdateWorkspace();this.Load();},
 OpenCreation(){this.setData({tab:'ai'});this.UpdateWorkspace();this.Load();},
 Noop(){},
 Filters(){this.setData({showFilters:true});},
 CloseFilters(){this.setData({showFilters:false});},
 CloseHistory(){this.setData({showHistory:false});},
 RefreshResults(){this.setData({resultHasMessage:this.data.messages.some((message:any)=>message.task?.id===(this.data.task as any)?.id&&message.task?.status==='succeeded'&&message.task?.result?.image_url),scrollTop:this.data.scrollTop+100000});},
 SessionMenu(){
  const actions=[{title:'新会话',run:()=>this.NewSession(),disabled:this.data.busy},{title:'查看额度',run:()=>this.QuotaDetails(),disabled:false},{title:'重命名',run:()=>this.RenameSession(),disabled:!this.data.sessionId},{title:'删除会话',run:()=>this.DeleteSession(),disabled:this.data.busy||!this.data.sessionId}].filter(action=>!action.disabled);
  wx.showActionSheet({itemList:actions.map(action=>action.title),success:choice=>{console.log('[开始] 图片会话菜单');Promise.resolve(actions[choice.tapIndex].run()).then(()=>console.log('[结束] 图片会话菜单'),fail);}});
 },
 ImageMenu(){wx.showActionSheet({itemList:['拍照','从手机相册选择','从我的照片选择'],success:choice=>{const actions=[()=>this.UploadFrom('camera'),()=>this.UploadFrom('album'),()=>this.ExistingImage()];console.log('[开始] 创作图片来源');actions[choice.tapIndex]().then(()=>console.log('[结束] 创作图片来源'),fail);}});},
 async UploadFrom(source:'camera'|'album'){const asset=await pickPhoto(source);this.setData({inputAsset:decorateAsset(asset)});},
 async ExistingImage(){const response:any=await request('/assets?source=photo&limit=100');this.setData({referencePhotos:response.items.map(decorateAsset),showPhotos:true});},
 ClosePhotos(){this.setData({showPhotos:false});},
 ChoosePhoto(event:any){const asset=this.data.referencePhotos.find((item:any)=>item.id===event.currentTarget.dataset.id);this.setData({inputAsset:asset,showPhotos:false});},
 SaveImage(event:any){this.SelectResult(event);return this.Save().then(undefined,fail);},
 ModifyImage(event:any){this.SelectResult(event);return this.ContinueImage().then(undefined,fail);},
 ResultMenu(event:any){this.SelectResult(event);wx.showActionSheet({itemList:['查看大图','重新生成','保存并加入观察点'],success:choice=>{const actions=[()=>preview((this.data.result as any).image_url),()=>this.Regenerate(),()=>this.AddResult()];console.log('[开始] 图片结果菜单');Promise.resolve(actions[choice.tapIndex]()).then(()=>console.log('[结束] 图片结果菜单'),fail);}});},
 QuotaDetails(){wx.showModal({title:'图片额度',content:'生图与笔记生成剩余 '+this.data.imageQuota+'%。正在处理的请求可能暂时占用部分额度，完成后按实际费用更新。',showCancel:false});},
 async Load(){
  const loadEpoch=++this._libraryEpoch,tab=this.data.tab;
  this.setData({loading:true,error:''});
  console.log('[开始] 素材页标题并行读取');
  if(currentProjectId()){
   console.log('[分支] 标题独立读取，不阻塞素材');
   getCurrentProject().then(project=>{
    console.log('[开始] 标题响应归属');
    if(loadEpoch===this._libraryEpoch&&!this.unloaded){console.log('[分支] 当前页面');this.setData({projectTitle:project.title});}
    else{console.log('[分支] 忽略旧页面');}
    console.log('[结束] 标题响应归属');
   },error=>{console.error('笔记名称读取失败：'+error.message);});
  }else{console.log('[分支] 未选择笔记');}
  console.log('[结束] 素材页标题并行读取');
  console.log('[开始] 素材页数据类型');
  if(tab==='ai'){
   console.log('[分支] 恢复创作；[结束] 素材页数据类型');
   await this.LoadSession().then(()=>this.setData({loading:false}),error=>this.setData({loading:false,error:error.message}));
   return;
  }
  console.log('[分支] 读取素材或模板；[结束] 素材页数据类型');
  const url=tab==='templates'?'/templates?'+query({q:this.data.q}):'/assets?'+query({q:this.data.q,category:this.data.category,source:this.data.source,unfiled:this.data.unfiled});
  await request(url).then(result=>{
   console.log('[开始] 素材列表响应归属');
   if(loadEpoch===this._libraryEpoch&&!this.unloaded){console.log('[分支] 更新当前列表');this.setData({items:tab==='templates'?result.items:result.items.map(decorateAsset),next:result.next_cursor||'',loading:false});}
   else{console.log('[分支] 忽略旧筛选结果');}
   console.log('[结束] 素材列表响应归属');
  },error=>{
   console.log('[开始] 素材列表失败归属');
   if(loadEpoch===this._libraryEpoch&&!this.unloaded){console.log('[分支] 显示读取失败');this.setData({loading:false,error:error.message});}
   else{console.log('[分支] 忽略旧页面失败');}
   console.log('[结束] 素材列表失败归属');
  });
 },
 async LoadSession(){
  const loadEpoch=this._generationEpoch;
  const [quotaRead]=await Promise.allSettled([request('/me/quota')]);
  console.log('[开始] 创作加载归属');
  if(loadEpoch!==this._generationEpoch){console.log('[分支] 忽略已切换会话；[结束] 创作加载归属；提前结束');return;}
  console.log('[分支] 当前会话；[结束] 创作加载归属');
  console.log('[开始] 创作额度读取');
  if(quotaRead.status==='fulfilled'){console.log('[分支] 更新额度');this.setData({imageQuota:quotaRead.value.items.find((item:any)=>item.provider==='image')?.remaining_percent??0});}
  else{console.log('[分支] 额度读取失败，继续恢复图片');}
  console.log('[结束] 创作额度读取');
  console.log('[开始] 创作会话恢复');
  if(this.data.sessionId||this._blankSession){
   console.log('[分支] 保留输入并刷新已选会话');
   console.log('[开始] 已选会话读取');
   if(this.data.sessionId&&!this.data.busy){console.log('[分支] 查询原会话最新任务');const session:any=await request('/sessions/'+this.data.sessionId);console.log('[开始] 已选会话响应归属');if(loadEpoch===this._generationEpoch){console.log('[分支] 恢复当前会话');this.RestoreSession(session);}else{console.log('[分支] 忽略已切换会话');}console.log('[结束] 已选会话响应归属');}else{console.log('[分支] 空白会话或已有查询进行中');}
   console.log('[结束] 已选会话读取');this.RestoreCreationDraft();this.RefreshResults();console.log('[结束] 创作会话恢复；提前结束');return;
  }
  console.log('[分支] 读取最近会话');const response:any=await request('/sessions');
  console.log('[开始] 最近会话检查');
  if(response.items?.length){console.log('[分支] 恢复最近创作');const session:any=await request('/sessions/'+response.items[0].id);
   console.log('[开始] 最近创作加载有效性');if(loadEpoch!==this._generationEpoch){console.log('[分支] 忽略旧会话');console.log('[结束] 最近创作加载有效性；提前结束');return;}console.log('[分支] 当前创作');console.log('[结束] 最近创作加载有效性');
   this.setData({sessions:response.items});this.RestoreSession(session);
  }else{console.log('[分支] 空白创作');}
  console.log('[结束] 最近会话检查');this.RestoreCreationDraft();this.RefreshResults();console.log('[结束] 创作会话恢复');
 },
 RestoreSession(session:any){
  const last=(session.messages||[]).slice().reverse().find((message:any)=>message.task)?.task;
  this.setData({sessionId:session.id,sessionTitle:session.title,messages:session.messages||[],task:last||null,result:last?.status==='succeeded'?last.result:null,error:last?.error?.message||''});
  this._lastGenerationInput=last?{...last.input}:null;this.RefreshResults();
  console.log('[开始] 会话任务恢复检查');
  if(last&&['queued','running'].includes(last.status)&&!this.data.busy){console.log('[分支] 自动查询原任务');const epoch=++this._generationEpoch;this.setData({busy:true,error:''});this.CompleteGeneration(last.id,session.id,epoch).then(undefined,(error:any)=>this.GenerationFailed(error,epoch));}
  else{console.log('[分支] 无待恢复任务或已有查询');}
  console.log('[结束] 会话任务恢复检查');
 },
 async SyncPending(){this.setData({syncing:true});try{await flushQueue();this.setData({pending:pendingPhotos()});await this.Load();}catch(e){fail(e);}finally{this.setData({syncing:false});}},
 ChangeTab(e:any){this.setData({tab:e.currentTarget.dataset.tab,q:'',items:[]});this.UpdateWorkspace();this.Load();},
 SearchInput(e:any){this.setData({q:e.detail.value});},Search(){this.Load();},
 Category(e:any){this.setData({category:e.currentTarget.dataset.value});this.Load();},
 Source(e:any){this.setData({source:e.currentTarget.dataset.value});this.Load();},
 async More(){try{const url=this.data.tab==='templates'?'/templates?':'/assets?';const r:any=await request(url+query({q:this.data.q,category:this.data.category,source:this.data.source,unfiled:this.data.unfiled,cursor:this.data.next}));this.setData({items:[...this.data.items,...(this.data.tab==='templates'?r.items:r.items.map(decorateAsset))],next:r.next_cursor||''});}catch(e){fail(e);}},
 async Template(e:any){try{const id=await chooseProject();go('/pages/canvas/index?projectId='+id+'&templateId='+e.currentTarget.dataset.id);}catch(e){fail(e);}},
 Asset(e:any){
 console.log('[开始] 素材点击方式');if(this.data.atlasTarget){console.log('[分支] 多选归档照片');const id=e.currentTarget.dataset.id;const selectedIds=this.data.selectedIds.includes(id)?this.data.selectedIds.filter((value:string)=>value!==id):[...this.data.selectedIds,id].slice(0,9);this.setData({selectedIds,items:this.data.items.map((item:any)=>({...item,selected:selectedIds.includes(item.id)}))});}else{console.log('[分支] 打开素材详情');go('/pages/asset/index?id='+e.currentTarget.dataset.id);}console.log('[结束] 素材点击方式');
 },
 ToggleUnfiled(){this.setData({unfiled:!this.data.unfiled,category:'all',source:'photo'});this.Load();},
 async ConfirmBatch(){const target:any=this.data.atlasTarget;const answer:any=await new Promise(resolve=>wx.showModal({title:'确认归类',content:'将 '+this.data.selectedIds.length+' 张照片加入 '+target.name+'。已属于其他物种的照片会移动归类，不调用 AI。',success:resolve}));console.log('[开始] 批量归档确认');if(!answer.confirm){console.log('[分支] 取消');console.log('[结束] 批量归档确认；提前结束');return;}console.log('[分支] 提交归档');console.log('[结束] 批量归档确认');await request('/species/'+target.id+'/photos','POST',{asset_ids:this.data.selectedIds}).then(()=>{localStore.Remove('atlasTarget');this.setData({atlasTarget:null,selectedIds:[]});go('/pages/species/index?id='+target.id);},fail);},
 CancelBatch(){localStore.Remove('atlasTarget');this.setData({atlasTarget:null,selectedIds:[]});},
 async ContinueImage(){const task:any=this.data.task;console.log('[开始] 连续改图结果检查');if(!task||task.status!=='succeeded'){console.log('[分支] 无可用生成图');console.log('[结束] 连续改图结果检查；提前结束');return;}console.log('[分支] 使用选中成图作为唯一参考');console.log('[结束] 连续改图结果检查');const asset:any=await request('/tasks/'+task.id+'/reference','POST');this.setData({inputAsset:asset,prompt:'',result:null,task:null});}
,
 async ChooseSession(){const result:any=await request('/sessions');this.setData({sessions:result.items,historyNext:result.next_cursor||'',showHistory:true});},
 MoreHistory(){request('/sessions?cursor='+encodeURIComponent(this.data.historyNext)).then((result:any)=>this.setData({sessions:[...this.data.sessions,...result.items],historyNext:result.next_cursor||''}),fail);},
 DeleteHistory(event:any){this.DeleteSession(event.currentTarget.dataset.id).then(undefined,fail);},
 async OpenSession(event:any){this.SaveCreationDraft();this._blankSession=false;const epoch=++this._generationEpoch;const session:any=await request('/sessions/'+event.currentTarget.dataset.id);console.log('[开始] 历史创作响应归属');if(epoch!==this._generationEpoch){console.log('[分支] 忽略旧会话；[结束] 历史创作响应归属；提前结束');return;}console.log('[分支] 当前会话；[结束] 历史创作响应归属');this.setData({busy:false,inputAsset:null,prompt:'',showHistory:false,error:''});this.RestoreSession(session);this.RestoreCreationDraft();},
 async RenameSession(){const answer:any=await new Promise(resolve=>wx.showModal({title:'会话名称',editable:true,placeholderText:this.data.sessionTitle,success:resolve}));console.log('[开始] 生图名称确认');if(answer.confirm&&answer.content?.trim()){console.log('[分支] 修改名称');await request('/sessions/'+this.data.sessionId,'PATCH',{title:answer.content.trim()});this.setData({sessionTitle:answer.content.trim()});}else{console.log('[分支] 取消');}console.log('[结束] 生图名称确认');},
 async DeleteSession(sessionId:string=this.data.sessionId){
  console.log('[开始] 创作删除许可');
  if(!sessionId||this.data.deletingId){console.log('[分支] 无会话或正在删除');console.log('[结束] 创作删除许可；提前结束');return;}
  console.log('[分支] 可以删除');console.log('[结束] 创作删除许可');
  const answer:any=await new Promise(resolve=>wx.showModal({title:'删除创作会话',content:'移除会话及未另存的结果，已保存的素材和笔记保留。删除内容按隐私政策保留于管理后台。',success:resolve}));
  console.log('[开始] 创作删除确认');
  if(!answer.confirm){console.log('[分支] 取消');console.log('[结束] 创作删除确认；提前结束');return;}
  console.log('[分支] 删除选中会话');console.log('[结束] 创作删除确认');this.setData({deletingId:sessionId});
  await request('/sessions/'+sessionId,'DELETE').then(()=>{
   localStore.Remove('nature:image-draft:'+sessionId);this.setData({sessions:this.data.sessions.filter((item:any)=>item.id!==sessionId),deletingId:''});
   console.log('[开始] 删除当前创作检查');
   if(this.data.sessionId===sessionId){console.log('[分支] 清空结果与输入');++this._generationEpoch;this._blankSession=true;this._lastGenerationInput=null;this.setData({sessionId:'',sessionTitle:'新创作',messages:[],result:null,task:null,inputAsset:null,prompt:'',busy:false,error:'',resultHasMessage:false});}else{console.log('[分支] 保留其他创作');}
   console.log('[结束] 删除当前创作检查');wx.showToast({title:'已删除'});
  },error=>{this.setData({deletingId:''});throw error;});
 },
 SelectResult(e:any){const message:any=this.data.messages.find((item:any)=>item.task?.id===e.currentTarget.dataset.id);console.log('[开始] 历史成图选择');if(message?.task?.status==='succeeded'){console.log('[分支] 选择生成结果');this._lastGenerationInput={...message.task.input};this.setData({task:message.task,result:message.task.result});}else{console.log('[分支] 保留当前结果');}this.RefreshResults();console.log('[结束] 历史成图选择');},
 async AddResult(){const taskId=(this.data.task as any)?.id;const asset:any=await request('/tasks/'+taskId+'/save','POST');await importAsset(asset.id);wx.showToast({title:'已保存并加入观察点'});},
 async DeleteAsset(event:any){
  const asset=this.data.items.find(item=>item.id===event.currentTarget.dataset.id);
  console.log('[开始] 素材删除互斥');
  if(!asset||this.data.removingAssetId){console.log('[分支] 等待当前删除；[结束] 素材删除互斥，提前结束');return;}
  console.log('[分支] 删除选择项；[结束] 素材删除互斥');this.setData({removingAssetId:asset.id});
  await DeleteMaterial(asset).then(async deleted=>{
   console.log('[开始] 素材列表同步');
   if(deleted){console.log('[分支] 清除选择并重新读取列表');this._libraryEpoch++;this.setData({items:this.data.items.filter(item=>item.id!==asset.id),selectedIds:this.data.selectedIds.filter(id=>id!==asset.id)});await this.Load();}
   else{console.log('[分支] 保留素材');}
   console.log('[结束] 素材列表同步');
  },fail).finally(()=>this.setData({removingAssetId:''}));
 },
 async Favorite(e:any){try{const id=e.currentTarget.dataset.id;const asset:any=this.data.items.find((x:any)=>x.id===id);await request('/assets/'+id+'/favorite','PUT',{favorite:!asset.favorite});this.setData({items:this.data.items.map((x:any)=>x.id===id?{...x,favorite:!x.favorite}:x)});}catch(e){fail(e);}},
 async Add(e:any){try{await importAsset(e.currentTarget.dataset.id);wx.showToast({title:'已加入观察点'});}catch(e){fail(e);}},
 async Choose(){try{await chooseProject();this.Load();}catch(e){fail(e);}},
 async Upload(){if(this.data.busy)return;try{const a=await pickPhoto();this.setData({inputAsset:decorateAsset(a),result:null,task:null});}catch(e){if(!(e as any).errMsg?.includes('cancel'))fail(e);}},
 RemoveReference(){if(this.data.busy)return;this._lastGenerationInput=null;this.setData({inputAsset:null,result:null,task:null,error:''});},
 Input(e:any){this.setData({prompt:e.detail.value});this.SaveCreationDraft();},
 Style(e:any){const s=this.data.styles[Number(e.detail.value)];this.setData({style:s.id,styleName:s.name});},
 async Send(){const epoch=this._generationEpoch+1;return this.StartGeneration(false).then(undefined,error=>this.GenerationFailed(error,epoch));},
 async Regenerate(){const epoch=this._generationEpoch+1;return this.StartGeneration(true).then(undefined,error=>this.GenerationFailed(error,epoch));},
 GenerationFailed(error:any,epoch:number){console.log('[开始] 创作错误归属');if(epoch===this._generationEpoch){console.log('[分支] 当前请求失败');this.setData({busy:false,error:error.message});fail(error);}else{console.log('[分支] 旧请求不影响当前输入');}console.log('[结束] 创作错误归属');},
 async StartGeneration(reuseLast:boolean){
  console.log('[开始] 创作提交检查');
  if(this.data.busy){console.log('[分支] 当前请求处理中');console.log('[结束] 创作提交检查；提前结束');return;}
  console.log('[分支] 可以提交');console.log('[结束] 创作提交检查');
  const previousTask:any=this.data.task;
  console.log('[开始] 原生图任务恢复检查');
  if(previousTask?.id&&['queued','running'].includes(previousTask.status)){
    console.log('[分支] 先取回已提交任务，禁止重复生成');
    const epoch=++this._generationEpoch;this.setData({busy:true,error:''});
    await this.CompleteGeneration(previousTask.id,previousTask.input?.session_id||this.data.sessionId,epoch);
    console.log('[结束] 原生图任务恢复检查；提前返回原结果');return;
  }else{console.log('[分支] 没有尚待查询的原任务');}
  console.log('[结束] 原生图任务恢复检查');
  const inputAsset:any=this.data.inputAsset;
  const freshInput={...(inputAsset?{asset_id:inputAsset.id}:{}),prompt:this.data.prompt.trim()||(inputAsset?'提取照片主体，保留可见外形，生成'+this.data.styleName+'素材':''),style_id:this.data.style};
  const input:any={...(reuseLast&&this._lastGenerationInput?this._lastGenerationInput:freshInput),session_id:this.data.sessionId};
  console.log('[开始] 创作内容检查');
  if(!input.prompt){console.log('[分支] 缺少文字或图片');wx.showToast({title:'请输入描述或添加参考图片',icon:'none'});console.log('[结束] 创作内容检查；提前结束');return;}
  console.log('[分支] 使用当前输入或选中图片的原始要求');console.log('[结束] 创作内容检查');
  const draftSessionId=this.data.sessionId;
  this.SaveCreationDraft();const epoch=++this._generationEpoch;this._lastGenerationInput={...input};this.setData({busy:true,error:'',result:null,task:null});
  console.log('[开始] 创作会话建立');
  if(!input.session_id){console.log('[分支] 新建会话');const session:any=await request('/sessions','POST',{title:input.prompt.slice(0,24)});input.session_id=session.id;this.setData({sessionId:session.id,sessionTitle:session.title,sessions:[session,...this.data.sessions]});}else{console.log('[分支] 沿用当前会话');}
  console.log('[结束] 创作会话建立');this._lastGenerationInput={...input};
  const task:any=await request('/tasks','POST',{kind:'image_generation',input,operation_id:operation()});
  console.log('[开始] 创作提交有效性');
  if(epoch!==this._generationEpoch){console.log('[分支] 等待已停止');await request('/tasks/'+task.id+'/cancel','POST');console.log('[结束] 创作提交有效性；提前结束');return;}
  console.log('[分支] 当前请求');console.log('[结束] 创作提交有效性');
  this.setData({task,messages:[...this.data.messages,{role:'user',text:input.prompt,image_url:reuseLast?'':inputAsset?.url||''}],prompt:'',inputAsset:null,scrollTop:this.data.scrollTop+100000});
  localStore.Remove('nature:image-draft:'+draftSessionId);
  localStore.Remove('nature:image-draft:'+input.session_id);await this.CompleteGeneration(task.id,input.session_id,epoch);
 },
 async CompleteGeneration(taskId:string,sessionId:string,epoch:number){
  const completed=await waitTask(taskId,(progress:any)=>{
    console.log('[开始] 生图查询进度归属');
    if(epoch===this._generationEpoch){console.log('[分支] 显示原任务及恢复状态');this.setData({task:progress,error:progress.error?.message||''});}
    else{console.log('[分支] 忽略旧会话进度');}
    console.log('[结束] 生图查询进度归属');
  });console.log('[开始] 创作结果归属');
  if(epoch===this._generationEpoch){
   console.log('[分支] 先显示已取得的图片，再同步历史和额度');
   this.setData({task:completed,result:completed.result,busy:false,error:'',messages:(this.data.messages||[]).map((message:any)=>message.task?.id===taskId?{...message,task:completed}:message)});this.RefreshResults();
   const [sessionRead,quotaRead]=await Promise.allSettled([request('/sessions/'+sessionId),request('/me/quota')]);
   console.log('[开始] 成图补充读取归属');
   if(epoch===this._generationEpoch){
    console.log('[分支] 当前会话');console.log('[开始] 成图历史读取');
    if(sessionRead.status==='fulfilled'){console.log('[分支] 更新历史');this.setData({messages:sessionRead.value.messages});}else{console.log('[分支] 历史读取失败，保留已取得图片');this.setData({error:'图片已生成，历史记录暂未同步：'+sessionRead.reason.message});}
    console.log('[结束] 成图历史读取');console.log('[开始] 成图额度读取');
    if(quotaRead.status==='fulfilled'){console.log('[分支] 更新额度');this.setData({imageQuota:quotaRead.value.items.find((item:any)=>item.provider==='image')?.remaining_percent??0});}else{console.log('[分支] 额度读取失败，保留已取得图片');this.setData({error:'图片已生成，额度暂未更新：'+quotaRead.reason.message});}
    console.log('[结束] 成图额度读取');this.RefreshResults();
   }else{console.log('[分支] 忽略其他会话的补充响应');}
   console.log('[结束] 成图补充读取归属');
  }else{console.log('[分支] 保留其他会话的状态');}
  console.log('[结束] 创作结果归属');
 },
 async Cancel(){const taskId=(this.data.task as any)?.id;++this._generationEpoch;this.setData({busy:false,result:null,task:null});if(!taskId)return;try{await request('/tasks/'+taskId+'/cancel','POST');}catch(e){fail(e);}},
 async Save(){console.log('[开始] 保存创作图片');if(this.data.busy||!this.data.result||(this.data.task as any)?.status!=='succeeded'){console.log('[分支] 当前没有可保存图片');console.log('[结束] 保存创作图片；提前结束');return;}console.log('[分支] 保存选中图片');const taskId=(this.data.task as any).id;const asset:any=await request('/tasks/'+taskId+'/save','POST');this.setData({messages:this.data.messages.map((message:any)=>message.task?.id===taskId?{...message,task:{...message.task,result:{...message.task.result,saved_asset_id:asset.id}}}:message)});console.log('[开始] 保存结果归属');if((this.data.task as any)?.id===taskId&&this.data.result){console.log('[分支] 更新选中图片');this.setData({result:{...(this.data.result as any),saved_asset_id:asset.id}});}else{console.log('[分支] 用户已选择其他图片');}console.log('[结束] 保存结果归属');wx.showToast({title:'已保存到素材库'});console.log('[结束] 保存创作图片');},
 Preview(e:any){preview(e.currentTarget.dataset.url);},
 NewSession(){console.log('[开始] 新创作许可');if(this.data.busy){console.log('[分支] 等待当前创作');console.log('[结束] 新创作许可；提前结束');return;}console.log('[分支] 清空工作区，发送时建立会话');console.log('[结束] 新创作许可');this.SaveCreationDraft();this._lastGenerationInput=null;this._blankSession=true;++this._generationEpoch;this.setData({sessionId:'',sessionTitle:'新创作',messages:[],result:null,task:null,inputAsset:null,prompt:'',showHistory:false,resultHasMessage:false,error:''});}
};
