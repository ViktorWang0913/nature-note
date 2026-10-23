import {request,errorMessage,operationId,waitForTask} from '../../services/api';
import {chooseProject,setCurrentProject} from '../../services/projects';
import * as localStore from '../../services/local-store';
import {Layout,SceneElement} from '../../types/models';
import {clone,History,fitViewport,screenToCanvas,hitElement,attachAsset,uid} from '../../engine/scene';
import {loadImages,renderScene} from '../../engine/render';
import {HitControl} from '../../engine/notebook-controls';
import drawingTools,{drawingData} from './drawing-tools';
import {defaultImageEdit} from '../../engine/image-adjustment';

// 画布和排版保存在内存中，只有明确保存时才写入笔记。
export default {
  data:{...drawingData,manual:false,layers:[],selectedLocked:false,backgroundColor:'#ffffff',projectId:'',title:'自然笔记',loading:true,busy:false,error:'',hasBackground:false,dirty:false,
    projectVersion:1,tracks:[] as any[],templates:[] as any[],trackIndex:0,templateIndex:0,description:'',
    panel:'',selectedId:'',selectedType:'',canUndo:false,canRedo:false,zoom:100,taskId:'',pendingTaskId:'',
    assets:[] as any[],assetSource:'generated',assetCursor:'',assetLoading:false,assetQuery:'',
    fonts:['简洁','书卷','等宽'],fontValues:['sans-serif','serif','monospace'],fontIndex:0,
    colors:['#253d32','#ffffff','#8a5234','#53755b','#324d76','#bd574a'],
    textForm:{text:'',fontSize:42,fontFamily:'sans-serif',fontWeight:'normal',textAlign:'left',color:'#253d32',textBackground:'transparent'},
    showCrop:false,cropSource:'',imageForm:{...defaultImageEdit},imageFields:[
      {key:'brightness',label:'亮度',min:0,max:200},{key:'contrast',label:'对比度',min:0,max:200},
      {key:'saturation',label:'饱和度',min:0,max:200}],
    imageFilters:[{key:'none',label:'原色'},{key:'warm',label:'暖色'},{key:'cool',label:'冷色'},{key:'grayscale',label:'黑白'}],
    showLeave:false,exportUrl:''},
  layout:null as Layout|null,history:null as History|null,savedSignature:'',canvas:null as any,context:null as any,
  images:new Map<string,any>(),viewport:{x:0,y:0,scale:1},canvasWidth:0,canvasHeight:0,pixelRatio:1,
  gesture:null as any,imageEditStart:null as Layout|null,renderEpoch:0,unloaded:false,resizeTimer:null as any,drawFrame:0,
  onLoad(options:any){this.Initialize(options).then(()=>{},error=>this.Fail(error));},
  async Initialize(options:any){
    this.images=new Map();
    const projectId=options.projectId||options.id||await chooseProject();
    this.setData({projectId});setCurrentProject(projectId);
    const [project,route,templates]=await Promise.all([request('/projects/'+projectId),request('/projects/'+projectId+'/route'),request('/templates?limit=100')]);
    console.log('[开始] 手动设计入口恢复');
    if(project.layout.designMode==='manual'){console.log('[分支] 打开独立设计；[结束] 手动设计入口恢复，提前结束');wx.redirectTo({url:'/pages/design/index?projectId='+projectId});return;}
    console.log('[分支] 观察笔记；[结束] 手动设计入口恢复');
    const tracks=route.tracks,choices=templates.items;
    const trackIndex=Math.max(0,tracks.findIndex((track:any)=>track.id===(options.trackId||route.draft.trackId)));
    const templateIndex=Math.max(0,choices.findIndex((template:any)=>template.id===(options.templateId||route.draft.templateId)));
    this.setData({busy:true,title:project.title,projectVersion:project.version,tracks,templates:choices,trackIndex,templateIndex,
      description:route.draft.description||'',pendingTaskId:route.latestTask?.id||''});
    console.log('[开始] 已保存排版读取');
    if(project.layout.notebookVersion===1){
      console.log('[分支] 恢复新版排版');this.layout=project.layout;this.history=new History(this.layout!);
      this.savedSignature=this.Signature();this.setData({hasBackground:true});
      await this.SetupCanvas();
    }else{console.log('[分支] 等待生成新背景');this.setData({panel:'background'});}
    console.log('[结束] 已保存排版读取');
    console.log('[开始] 环境描述初始化');
    if(!this.data.description){console.log('[分支] 从观察文字准备描述');this.DescribeTrack();}
    else{console.log('[分支] 使用已确认描述');}
    console.log('[结束] 环境描述初始化');
    console.log('[开始] 最新背景恢复入口');
    if(route.latestTask?.id===project.layout.backgroundTaskId||['failed','cancelled'].includes(route.latestTask?.status)){
      console.log('[分支] 已使用或已失败，不显示恢复');this.setData({pendingTaskId:''});
    }else{console.log('[分支] 可查看未应用结果');}
    console.log('[结束] 最新背景恢复入口');
    console.log('[开始] 上次背景失败提示');
    if(route.latestTask?.status==='failed'){
      console.log('[分支] 保留上次失败说明及任务编号');
      this.setData({error:(route.latestTask.error?.message||'上次背景生成未完成')+'。任务编号：'+route.latestTask.id+'。请先核对原任务及费用。'});
    }else{console.log('[分支] 无失败需要提示');}
    console.log('[结束] 上次背景失败提示');
    this.setData({loading:false,busy:false});
  },
  onUnload(){this.unloaded=true;this.renderEpoch++;clearTimeout(this.resizeTimer);cancelAnimationFrame(this.drawFrame);this.images.clear();},
  onShow(){
    console.log('[开始] 观察记录返回检查');
    if(this.data.projectId&&!this.data.loading&&!this.data.busy){
      console.log('[分支] 刷新可选记录');request('/projects/'+this.data.projectId+'/route').then(route=>{
        this.setData({tracks:route.tracks,trackIndex:Math.min(this.data.trackIndex,Math.max(0,route.tracks.length-1))});
      },error=>this.Fail(error));
    }else{console.log('[分支] 等待初始化或当前操作');}
    console.log('[结束] 观察记录返回检查');
  },
  onResize(){this.ScheduleCanvas();},
  ScheduleCanvas(){
    clearTimeout(this.resizeTimer);
    this.resizeTimer=setTimeout(()=>{
      console.log('[开始] 画布尺寸变更');
      if(this.data.hasBackground&&!this.unloaded){console.log('[分支] 布局稳定后重新适配');this.SetupCanvas().then(()=>{},error=>this.Fail(error));}
      else{console.log('[分支] 尚无画布或页面已关闭');}
      console.log('[结束] 画布尺寸变更');
    },220);
  },
  Fail(error:any){console.log('[开始] 错误展示');if(!this.unloaded){console.log('[分支] 显示失败原因');this.setData({busy:false,loading:false,assetLoading:false,error:errorMessage(error)});}else{console.log('[分支] 页面已离开');}console.log('[结束] 错误展示');},
  DescribeTrack(){
    const track=this.data.tracks[this.data.trackIndex];
    console.log('[开始] 环境文字整理');
    if(!track){console.log('[分支] 暂无已结束记录');console.log('[结束] 环境文字整理；提前结束');return;}
    console.log('[分支] 仅整理地点与观察文字');
    const parts=track.nodes.map((node:any,index:number)=>'沿途位置 '+(index+1)+'：'+(node.place_name||'未命名地点')+'。'+(node.text||''));
    this.setData({description:parts.join('\n')});console.log('[结束] 环境文字整理');
  },
  TrackChanged(event:any){this.setData({trackIndex:Number(event.detail.value)});this.DescribeTrack();},
  TemplateChanged(event:any){this.setData({templateIndex:Number(event.detail.value)});},
  DescriptionInput(event:any){this.setData({description:event.detail.value});},
  Background(){this.setData({panel:'background',error:''});},
  ClosePanel(){
    this.FinishStyle();
    console.log('[开始] 图片调整取消检查');
    if(this.imageEditStart){console.log('[分支] 恢复应用前排版');this.layout=this.imageEditStart;this.imageEditStart=null;this.Draw();}
    else{console.log('[分支] 关闭普通面板');}
    console.log('[结束] 图片调整取消检查');this.setData({panel:''});wx.hideKeyboard();this.ScheduleCanvas();
  },
  EditMaterial(){
    const element=this.layout?.elements.find(item=>item.id===this.data.selectedId&&item.id!=='background'&&item.type==='image');
    console.log('[开始] 画布素材编辑检查');
    if(!element||element.locked||this.data.busy){console.log('[分支] 没有可编辑素材；[结束] 画布素材编辑检查，提前结束');return;}
    console.log('[分支] 在背景上编辑素材；[结束] 画布素材编辑检查');
    this.TouchEnd();this.imageEditStart=clone(this.layout);
    this.setData({panel:'image',cropSource:element.url,showCrop:false,imageForm:{...defaultImageEdit,...element.imageEdit}});this.ScheduleCanvas();
  },
  OpenCrop(){this.setData({showCrop:true});},
  CloseCrop(){this.setData({showCrop:false});},
  ApplyCrop(event:any){this.setData({imageForm:{...this.data.imageForm,...event.detail},showCrop:false});this.PreviewMaterial();},
  AdjustMaterial(event:any){
    const field=event.currentTarget.dataset.field,value=Number(event.detail.value),form={...this.data.imageForm,[field]:value};
    this.setData({imageForm:form});this.PreviewMaterial();
  },
  FilterMaterial(event:any){this.setData({imageForm:{...this.data.imageForm,filter:event.currentTarget.dataset.value}});this.PreviewMaterial();},
  ResetMaterial(){this.setData({imageForm:{...defaultImageEdit}});this.PreviewMaterial();},
  PreviewMaterial(){
    const element=this.layout!.elements.find(item=>item.id===this.data.selectedId)!;
    element.imageEdit={...this.data.imageForm};this.Draw();
  },
  ApplyMaterial(){this.PreviewMaterial();this.imageEditStart=null;this.Commit(this.layout!);this.ClosePanel();},
  Noop(){},
  Record(){wx.navigateTo({url:'/pages/gps/index?projectId='+this.data.projectId});},
  Generate(){this.GenerateBackground().then(()=>{},error=>this.Fail(error));},
  async GenerateBackground(){
    console.log('[开始] 背景生成准备');
    if(this.data.busy||!this.data.tracks.length||!this.data.templates.length||!this.data.description.trim()){
      console.log('[分支] 等待完整输入；[结束] 背景生成准备，提前结束');return;
    }
    console.log('[分支] 输入完整；[结束] 背景生成准备');
    console.log('[开始] 重建排版确认');
    if(this.data.hasBackground){
      console.log('[分支] 提醒成功后清空排版');
      const answer:any=await new Promise(resolve=>wx.showModal({title:'重新生成背景',content:'新背景生成成功后，当前素材和文字会被清空。生成失败会保留当前设计。',success:resolve}));
      console.log('[开始] 重建确认结果');
      if(!answer.confirm){console.log('[分支] 已取消；[结束] 重建确认结果；[结束] 重建排版确认，提前结束');return;}
      console.log('[分支] 已确认；[结束] 重建确认结果');
    }else{console.log('[分支] 首次生成');}
    console.log('[结束] 重建排版确认');this.setData({busy:true,error:''});
    console.log('[开始] 上次任务状态核对');
    if(this.data.pendingTaskId){
      console.log('[分支] 查询已提交任务');
      const previous=await request('/tasks/'+this.data.pendingTaskId);
      console.log('[开始] 已有任务可恢复检查');
      if(['queued','running','succeeded'].includes(previous.status)){
        console.log('[分支] 复用已有任务；[结束] 已有任务可恢复检查；[结束] 上次任务状态核对，提前结束新提交');
        await this.CompleteBackground(previous.id);return;
      }
      console.log('[分支] 上次已失败，可提交新任务；[结束] 已有任务可恢复检查');this.setData({pendingTaskId:''});
    }else{console.log('[分支] 无待恢复任务');}
    console.log('[结束] 上次任务状态核对');
    // Unknown submission outcomes reuse the same idempotency key and immutable draft.
    const pendingKey='nature:background-operation:'+this.data.projectId;
    let pending=localStore.Get(pendingKey);
    console.log('[开始] 未确认提交检查');
    if(!pending){
      console.log('[分支] 保存本次确认的描述');
      const saved=await request('/projects/'+this.data.projectId+'/route','PUT',{baseVersion:this.data.projectVersion,
        trackId:this.data.tracks[this.data.trackIndex].id,templateId:this.data.templates[this.data.templateIndex].id,description:this.data.description});
      this.setData({projectVersion:saved.projectVersion});
      pending={operation_id:operationId(),kind:'image_polish',input:{project_id:this.data.projectId,draftVersion:saved.draft.version,confirmed:true}};
      localStore.Set(pendingKey,pending);
    }else{console.log('[分支] 查询原提交，避免重复扣费');}
    console.log('[结束] 未确认提交检查');
    const task=await request('/tasks','POST',pending);localStore.Remove(pendingKey);
    this.setData({taskId:task.id,pendingTaskId:task.id});await this.CompleteBackground(task.id);
  },
  Resume(){this.ResumeBackground().then(()=>{},error=>this.Fail(error));},
  async ResumeBackground(){
    console.log('[开始] 恢复背景覆盖确认');
    if(this.data.hasBackground){
      console.log('[分支] 先确认清空当前设计');
      const answer:any=await new Promise(resolve=>wx.showModal({title:'使用新背景',content:'背景加载成功后会清空当前素材和文字。',success:resolve}));
      console.log('[开始] 恢复确认');if(!answer.confirm){console.log('[分支] 取消；[结束] 恢复确认；[结束] 恢复背景覆盖确认，提前结束');return;}
      console.log('[分支] 确认；[结束] 恢复确认');
    }else{console.log('[分支] 尚无设计');}
    console.log('[结束] 恢复背景覆盖确认');this.setData({busy:true,error:''});await this.CompleteBackground(this.data.pendingTaskId);
  },
  async CompleteBackground(taskId:string){
    const task=await waitForTask(taskId);
    const asset=await request('/tasks/'+task.id+'/save','POST');
    const next:Layout={schema_version:1,notebookVersion:1,backgroundTaskId:task.id,width:1024,height:1536,background:'#ffffff',elements:[
      {id:'background',type:'image',asset_id:asset.id,url:asset.url,x:0,y:0,width:1024,height:1536,rotation:0,z:0}]};
    console.log('[开始] 背景加载前页面检查');
    if(this.unloaded){console.log('[分支] 离开后保留服务端结果；[结束] 背景加载前页面检查，提前结束');return;}
    console.log('[分支] 准备画布；[结束] 背景加载前页面检查');
    // Preload before replacing the current layout; download failure leaves the design intact.
    const imageCanvas=this.canvas||wx.createOffscreenCanvas({type:'2d',width:1024,height:1536});
    const loaded=await loadImages(imageCanvas,next);this.images=loaded;
    this.layout=next;this.history=new History(next);
    this.setData({hasBackground:true,panel:'',selectedId:'',selectedType:'',pendingTaskId:'',taskId:''});
    this.UpdateDirty();await this.SetupCanvas();this.setData({busy:false});
  },
  async SetupCanvas(){
    await new Promise<void>(resolve=>wx.nextTick(resolve));
    const result:any=await new Promise(resolve=>this.createSelectorQuery().select('#notebook').fields({node:true,size:true}).exec(items=>resolve(items[0])));
    console.log('[开始] 画布节点检查');
    if(!result?.node||!this.layout||this.unloaded){console.log('[分支] 页面尚未就绪；[结束] 画布节点检查，提前结束');return;}
    console.log('[分支] 画布可用；[结束] 画布节点检查');
    console.log('[开始] 活动手势尺寸保护');
    if(this.gesture||this.drawingGesture||this.manipulation){console.log('[分支] 延后尺寸更新；[结束] 活动手势尺寸保护，提前结束');this.ScheduleCanvas();return;}
    console.log('[分支] 可以更新尺寸；[结束] 活动手势尺寸保护');
    console.log('[开始] 画布尺寸缓存检查');
    if(this.canvas===result.node&&this.canvasWidth===result.width&&this.canvasHeight===result.height){
      console.log('[分支] 尺寸未变，保留缩放与图片；[结束] 画布尺寸缓存检查，提前结束');this.Draw();return;
    }
    console.log('[分支] 适配新尺寸；[结束] 画布尺寸缓存检查');
    const previousCanvas=this.canvas;
    const previousWidth=this.canvasWidth,previousHeight=this.canvasHeight;
    const previousViewport={...this.viewport};
    this.canvas=result.node;this.canvasWidth=result.width;this.canvasHeight=result.height;this.pixelRatio=wx.getWindowInfo().pixelRatio;
    this.canvas.width=Math.round(result.width*this.pixelRatio);this.canvas.height=Math.round(result.height*this.pixelRatio);
    this.context=this.canvas.getContext('2d');
    console.log('[开始] 保留画布视图');
    if(previousCanvas&&previousWidth&&previousHeight){
      console.log('[分支] 保留实际倍率与画面中心');
      this.viewport={scale:previousViewport.scale,x:previousViewport.x+(result.width-previousWidth)/2,y:previousViewport.y+(result.height-previousHeight)/2};
      this.setData({zoom:Math.round(this.viewport.scale/fitViewport(this.layout,result.width,result.height,12).scale*100)});
    }else{console.log('[分支] 首次适合屏幕');this.Fit();}
    console.log('[结束] 保留画布视图');
    console.log('[开始] 图片对象复用检查');
    if(previousCanvas===this.canvas&&this.images.size){console.log('[分支] 复用已加载图片');}
    else{console.log('[分支] 首次加载画布图片');await this.RefreshImages();}
    console.log('[结束] 图片对象复用检查');this.Draw();
  },
  async RefreshImages(){
    const epoch=++this.renderEpoch;const loaded=await loadImages(this.canvas,this.layout!,this.images);
    console.log('[开始] 图片加载版本检查');
    if(epoch===this.renderEpoch&&!this.unloaded){console.log('[分支] 应用当前图片');this.images=loaded;this.Draw();}
    else{console.log('[分支] 丢弃已过期画布加载');}
    console.log('[结束] 图片加载版本检查');
  },
  Draw(){
    console.log('[开始] 合并画布绘制');
    if(this.drawFrame||this.unloaded){console.log('[分支] 已排入下一帧或页面已关闭；[结束] 合并画布绘制，提前结束');return;}
    console.log('[分支] 下一帧绘制最新状态；[结束] 合并画布绘制');
    this.drawFrame=requestAnimationFrame(()=>{this.drawFrame=0;this.DrawNow();});
  },
  DrawNow(){
    console.log('[开始] 画布绘制检查');
    if(!this.context||!this.layout){console.log('[分支] 尚未就绪；[结束] 画布绘制检查，提前结束');return;}
    console.log('[分支] 绘制当前设计；[结束] 画布绘制检查');
    const ctx=this.context;ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,this.canvas.width,this.canvas.height);
    ctx.scale(this.pixelRatio,this.pixelRatio);
    ctx.save();ctx.shadowColor='rgba(28,50,35,.22)';ctx.shadowBlur=8;ctx.fillStyle=this.layout.background;
    ctx.fillRect(this.viewport.x,this.viewport.y,this.layout.width*this.viewport.scale,this.layout.height*this.viewport.scale);ctx.restore();
    renderScene(ctx,this.layout,this.images,{viewport:this.viewport,selectedId:this.data.selectedId,controlSize:{width:this.canvasWidth,height:this.canvasHeight}});
  },
  Fit(){this.viewport=fitViewport(this.layout!,this.canvasWidth,this.canvasHeight,12);this.setData({zoom:100});this.Draw();},
  Select(id:string){const element=this.layout?.elements.find(item=>item.id===id);this.setData({selectedId:id,selectedType:element?.type||''});this.SyncDrawingState();this.Draw();},
  Deselect(){this.Select('');},
  CanvasTouchStart(event:any){
    const touches=event.touches;
    console.log('[开始] 画布输入就绪检查');
    if(!this.layout||this.data.busy||this.data.panel==='image'||!touches.length||touches.length>2){console.log('[分支] 忽略不可用输入；[结束] 画布输入就绪检查，提前结束');return;}
    console.log('[分支] 可编辑画布；[结束] 画布输入就绪检查');
    // 加入第二根手指前提交已有拖动，避免覆盖尚未记录的操作。
    this.CanvasTouchEnd();
    const first={x:touches[0].x,y:touches[0].y};
    const selected=this.layout.elements.find(item=>item.id===this.data.selectedId);
    const control=selected&&touches.length===1?HitControl(this.layout,selected,screenToCanvas(first,this.viewport),this.viewport,{width:this.canvasWidth,height:this.canvasHeight}):'';
    console.log('[开始] 单指对象命中');
    if(touches.length===1&&!control&&!event.preserveSelection){
      console.log('[分支] 选择素材或文字');const hit=hitElement(this.layout!,screenToCanvas(first,this.viewport));
      this.Select(hit?.id==='background'?'':hit?.id||'');
    }else{console.log('[分支] 双指保留选择');}
    console.log('[结束] 单指对象命中');
    const second=touches[1]||touches[0];
    this.gesture={layout:clone(this.layout),viewport:{...this.viewport},count:touches.length,
      control,selectedId:this.layout.elements.find(item=>item.id===this.data.selectedId)?.locked?'':this.data.selectedId,
      center:{x:(first.x+second.x)/2,y:(first.y+second.y)/2},distance:Math.max(1,Math.hypot(second.x-first.x,second.y-first.y)),
      angle:Math.atan2(second.y-first.y,second.x-first.x),changed:false};
  },
  CanvasTouchMove(event:any){
    const gesture=this.gesture,touches=event.touches;
    console.log('[开始] 手势状态检查');
    if(!gesture||!touches.length||touches.length>2){console.log('[分支] 无有效起点或手指数；[结束] 手势状态检查，提前结束');return;}
    console.log('[分支] 处理拖动；[结束] 手势状态检查');
    console.log('[开始] 手指数变化');
    if(gesture.count!==touches.length){console.log('[分支] 重设手势起点');this.TouchStart({...event,preserveSelection:true});console.log('[结束] 手指数变化，提前结束');return;}
    console.log('[分支] 手指数一致；[结束] 手指数变化');
    const first=touches[0],second=touches[1]||first,center={x:(first.x+second.x)/2,y:(first.y+second.y)/2};
    let factor=touches.length===2?Math.hypot(second.x-first.x,second.y-first.y)/gesture.distance:1;
    let angle=touches.length===2?(Math.atan2(second.y-first.y,second.x-first.x)-gesture.angle)*180/Math.PI:0;
    console.log('[开始] 手势操作目标');
    if(gesture.selectedId){
      console.log('[分支] 变换选中对象');
      const next=clone(gesture.layout),element=next.elements.find((item:SceneElement)=>item.id===gesture.selectedId)!;
      let start=screenToCanvas(gesture.center,gesture.viewport),end=screenToCanvas(center,gesture.viewport);
      console.log('[开始] 单指控制柄变换');
      if(gesture.control&&gesture.control!=='move'){
        console.log('[分支] 围绕素材中心缩放或旋转');
        const pivot={x:element.x+element.width/2,y:element.y+element.height/2};
        factor=gesture.control==='scale'?Math.hypot(end.x-pivot.x,end.y-pivot.y)/Math.max(1,Math.hypot(start.x-pivot.x,start.y-pivot.y)):1;
        angle=gesture.control==='rotate'?(Math.atan2(end.y-pivot.y,end.x-pivot.x)-Math.atan2(start.y-pivot.y,start.x-pivot.x))*180/Math.PI:0;
        start=pivot;end=pivot;
      }else{console.log('[分支] 拖动或双指变换');}
      console.log('[结束] 单指控制柄变换');
      const minimum=Math.max(16/element.width,16/element.height,element.type==='text'?8/element.fontSize:0);
      const maximum=Math.min(5000/element.width,5000/element.height,element.type==='text'?240/element.fontSize:100);
      const scale=factor===1?1:Math.max(minimum,Math.min(maximum,factor)),radians=angle*Math.PI/180;
      const dx=element.x+element.width/2-start.x,dy=element.y+element.height/2-start.y;
      element.width*=scale;element.height*=scale;
      element.x=end.x+(dx*Math.cos(radians)-dy*Math.sin(radians))*scale-element.width/2;
      element.y=end.y+(dx*Math.sin(radians)+dy*Math.cos(radians))*scale-element.height/2;
      element.rotation=(element.rotation+angle)%360;
      console.log('[开始] 文字缩放');if(element.type==='text'){console.log('[分支] 字号同步');element.fontSize*=scale;}else{console.log('[分支] 图片保持比例');}console.log('[结束] 文字缩放');
      this.layout=next;gesture.changed=true;
    }else{
      console.log('[分支] 移动或缩放画布');
      const fit=fitViewport(this.layout!,this.canvasWidth,this.canvasHeight,12).scale;
      const scale=Math.max(fit*.5,Math.min(fit*6,gesture.viewport.scale*factor));
      const anchor=screenToCanvas(gesture.center,gesture.viewport);
      this.viewport={scale,x:center.x-anchor.x*scale,y:center.y-anchor.y*scale};this.setData({zoom:Math.round(scale/fit*100)});
    }
    console.log('[结束] 手势操作目标');this.Draw();
  },
  CanvasTouchEnd(event?:any){
    console.log('[开始] 手势提交');
    if(this.gesture?.changed){console.log('[分支] 记录一次撤销');this.Commit(this.layout!);}
    else{console.log('[分支] 仅选择或浏览');}
    console.log('[结束] 手势提交');this.gesture=null;
    console.log('[开始] 剩余手指继续操作');
    if(event?.touches?.length){console.log('[分支] 以当前位置重新开始');this.TouchStart({...event,preserveSelection:true});}
    else{console.log('[分支] 手势结束');}
    console.log('[结束] 剩余手指继续操作');
  },
  Commit(next:Layout){this.layout=next;this.history!.commit(next);this.UpdateDirty();this.Draw();},
  UpdateDirty(){
    this.SyncDrawingState();
    const dirty=this.Signature()!==this.savedSignature;
    this.setData({dirty,canUndo:!!this.history?.canUndo,canRedo:!!this.history?.canRedo});
    console.log('[开始] 未保存离开保护');
    if(dirty){console.log('[分支] 开启系统离开提醒');wx.enableAlertBeforeUnload({message:'设计尚未保存，离开会丢失本次修改。'});}
    else{console.log('[分支] 已保存');wx.disableAlertBeforeUnload();}
    console.log('[结束] 未保存离开保护');
  },
  Signature(){return JSON.stringify(this.layout,(key,value)=>key==='url'?undefined:value);},
  Undo(){this.TouchEnd();this.FinishStyle();this.layout=this.history!.undo();this.Select('');this.UpdateDirty();this.RefreshImages().then(()=>{},error=>this.Fail(error));},
  Redo(){this.TouchEnd();this.FinishStyle();this.layout=this.history!.redo();this.Select('');this.UpdateDirty();this.RefreshImages().then(()=>{},error=>this.Fail(error));},
  Materials(){this.FinishDrawing();this.setData({panel:'materials',assets:[],assetCursor:''});this.LoadAssets(false).then(()=>{},error=>this.Fail(error));},
  AssetSource(event:any){this.setData({assetSource:event.currentTarget.dataset.source,assets:[],assetCursor:''});this.LoadAssets(false).then(()=>{},error=>this.Fail(error));},
  AssetSearch(event:any){this.setData({assetQuery:event.detail.value});},
  SearchAssets(){this.LoadAssets(false).then(()=>{},error=>this.Fail(error));},
  MoreAssets(){console.log('[开始] 素材翻页');if(this.data.assetCursor&&!this.data.assetLoading){console.log('[分支] 加载下一页');this.LoadAssets(true).then(()=>{},error=>this.Fail(error));}else{console.log('[分支] 无下一页或正在加载');}console.log('[结束] 素材翻页');},
  async LoadAssets(append:boolean){
    this.setData({assetLoading:true,error:''});const source=this.data.assetSource;
    const response=await request('/assets?source='+source+'&q='+encodeURIComponent(this.data.assetQuery)+'&limit=30'+(append?'&cursor='+encodeURIComponent(this.data.assetCursor):''));
    console.log('[开始] 素材列表响应检查');
    if(source===this.data.assetSource){console.log('[分支] 更新当前分类');this.setData({assets:append?this.data.assets.concat(response.items):response.items,assetCursor:response.next_cursor||'',assetLoading:false});}
    else{console.log('[分支] 忽略旧分类响应');}
    console.log('[结束] 素材列表响应检查');
  },
  AddAsset(event:any){this.InsertAsset(event.currentTarget.dataset.id).then(()=>{},error=>this.Fail(error));},
  async InsertAsset(id:string){
    console.log('[开始] 素材插入互斥');
    if(this.data.busy){console.log('[分支] 正在插入；[结束] 素材插入互斥，提前结束');return;}
    console.log('[分支] 开始插入；[结束] 素材插入互斥');this.setData({busy:true});
    const asset=this.data.assets.find(item=>item.id===id);
    const center=screenToCanvas({x:this.canvasWidth/2,y:this.canvasHeight/2},this.viewport);
    center.x=Math.max(0,Math.min(1024,center.x));center.y=Math.max(0,Math.min(1536,center.y));
    const next=attachAsset(this.layout!,asset,center);
    const loaded=await loadImages(this.canvas,next,this.images);this.images=loaded;
    this.Commit(next);this.setData({panel:this.data.manual&&window.innerWidth>=900?'materials':'',busy:false});this.Select(next.elements[next.elements.length-1].id);
  },
  Text(){
    this.FinishDrawing();
    const element=this.layout!.elements.find(item=>item.id===this.data.selectedId&&item.type==='text');
    this.setData({panel:'text',fontIndex:Math.max(0,this.data.fontValues.indexOf(element?.fontFamily||'sans-serif')),
      textForm:{text:element?.text||'',fontSize:element?.fontSize||42,fontFamily:element?.fontFamily||'sans-serif',fontWeight:element?.fontWeight||'normal',
        textAlign:element?.textAlign||'left',color:element?.color||'#253d32',textBackground:element?.textBackground||'transparent'}});
  },
  TextInput(event:any){this.setData({'textForm.text':event.detail.value});},
  FontChanged(event:any){const index=Number(event.detail.value);this.setData({fontIndex:index,'textForm.fontFamily':this.data.fontValues[index]});},
  FontSize(event:any){this.setData({'textForm.fontSize':Number(event.detail.value)});},
  TextStyle(event:any){const {field,value}=event.currentTarget.dataset;this.setData({['textForm.'+field]:value});},
  Bold(){this.setData({'textForm.fontWeight':this.data.textForm.fontWeight==='bold'?'normal':'bold'});},
  ApplyText(){
    console.log('[开始] 文字内容检查');if(!this.data.textForm.text.trim()){console.log('[分支] 等待文字；[结束] 文字内容检查，提前结束');return;}
    console.log('[分支] 应用文字；[结束] 文字内容检查');
    const next=clone(this.layout!),center=screenToCanvas({x:this.canvasWidth/2,y:this.canvasHeight/2},this.viewport);
    let element=next.elements.find(item=>item.id===this.data.selectedId&&item.type==='text');
    console.log('[开始] 新建或编辑文字');
    if(!element){console.log('[分支] 新建文字');element={id:uid('text'),type:'text',x:center.x-240,y:center.y-120,width:480,height:240,rotation:0,z:Math.max(0,...next.elements.map(item=>item.z))+1};next.elements.push(element);}
    else{console.log('[分支] 修改当前文字');}
    console.log('[结束] 新建或编辑文字');Object.assign(element,this.data.textForm);
    const ctx=this.context;ctx.font=`${element.fontWeight} ${element.fontSize}px ${element.fontFamily}`;
    let lineText='',lineCount=1;const characters=Array.from(String(element.text));
    console.log('[开始] 文字高度计算，共 '+characters.length+' 字');
    characters.forEach((character,index)=>{
      console.log('[开始] 字符 '+(index+1)+'/'+characters.length);console.log('[开始] 行宽检查');
      if(character==='\n'||(lineText&&ctx.measureText(lineText+character).width>element!.width)){console.log('[分支] 换行');lineCount++;lineText='';}
      else{console.log('[分支] 同一行');}
      console.log('[结束] 行宽检查');lineText+=character.replace('\n','');console.log('[结束] 字符 '+(index+1)+'/'+characters.length);
    });
    console.log('[结束] 文字高度计算');element.height=Math.ceil(lineCount*element.fontSize!*1.45+element.fontSize!*.2);
    console.log('[开始] 文字长度边界检查');
    if(element.height>10000){console.log('[分支] 文本过长；[结束] 文字长度边界检查，提前结束');this.setData({error:'文字过长，请缩短内容或减小字号'});return;}
    console.log('[分支] 文字完整可排版；[结束] 文字长度边界检查');this.Commit(next);this.Select(element.id);this.ClosePanel();
  },
  Remove(){
    console.log('[开始] 删除画布元素许可');
    if(this.data.busy||this.layout?.elements.find(item=>item.id===this.data.selectedId)?.locked){console.log('[分支] 元素锁定或正在处理；[结束] 删除画布元素许可，提前结束');return;}
    console.log('[分支] 删除当前元素；[结束] 删除画布元素许可');const next=clone(this.layout!);next.elements=next.elements.filter(item=>item.id!==this.data.selectedId||item.id==='background');this.Commit(next);this.Select('');},
  Layers(){wx.showActionSheet({itemList:['上移一层','下移一层','移至顶层','移至底层'],success:answer=>this.MoveLayer(answer.tapIndex)});},
  MoveLayer(action:number){
    const next=clone(this.layout!),objects=next.elements.filter(item=>item.id!=='background').sort((first,second)=>first.z-second.z);
    const index=objects.findIndex(item=>item.id===this.data.selectedId),element=objects.splice(index,1)[0];
    const target=[Math.min(objects.length,index+1),Math.max(0,index-1),objects.length,0][action];objects.splice(target,0,element);
    console.log('[开始] 图层排序，共 '+objects.length+' 层');objects.forEach((item,index)=>{console.log('[开始] 图层 '+(index+1)+'/'+objects.length);item.z=index+1;console.log('[结束] 图层 '+(index+1)+'/'+objects.length);});console.log('[结束] 图层排序');this.Commit(next);
  },
  Save(){this.SaveDesign().then(()=>{},error=>this.Fail(error));},
  async SaveDesign(){
    this.PrepareSave();
    this.setData({busy:true,error:''});
    const response=await request('/projects/'+this.data.projectId,'PATCH',{base_version:this.data.projectVersion,layout:this.layout});
    this.layout=response.layout;this.savedSignature=this.Signature();
    this.setData({projectVersion:response.version,busy:false});this.UpdateDirty();await this.RefreshImages();wx.showToast({title:'已保存'});
  },
  Export(){this.ExportImage().then(()=>{},error=>this.Fail(error));},
  async ExportImage(){
    this.PrepareSave();
    this.setData({busy:true,error:''});
    const resultNode:any=await new Promise(resolve=>this.createSelectorQuery().select('#export-canvas').fields({node:true}).exec(items=>resolve(items[0])));
    const canvas=resultNode.node;canvas.width=this.layout!.width;canvas.height=this.layout!.height;
    const images=await loadImages(canvas,this.layout!,this.images);renderScene(canvas.getContext('2d'),this.layout!,images);
    const result:any=await new Promise((resolve,reject)=>wx.canvasToTempFilePath({canvas,width:canvas.width,height:canvas.height,destWidth:canvas.width,destHeight:canvas.height,fileType:'png',success:resolve,fail:reject} as any));
    this.setData({busy:false,exportUrl:result.tempFilePath,panel:'export'});
  },
  SaveAlbum(){wx.saveImageToPhotosAlbum({filePath:this.data.exportUrl,success:()=>wx.showToast({title:'已打开保存或分享'}),fail:error=>this.Fail(error)});},
  Leave(){
    this.TouchEnd();
    console.log('[开始] 退出素材调整检查');
    if(this.imageEditStart){console.log('[分支] 取消本次预览，返回画布；[结束] 退出素材调整检查，提前结束');this.ClosePanel();return;}
    console.log('[分支] 普通画布返回；[结束] 退出素材调整检查');
    console.log('[开始] 返回保存检查');if(this.data.dirty){console.log('[分支] 显示三项选择');this.setData({showLeave:true});}else{console.log('[分支] 直接返回');this.GoBack();}console.log('[结束] 返回保存检查');
  },
  Stay(){this.setData({showLeave:false});},
  Discard(){wx.disableAlertBeforeUnload();this.GoBack();},
  SaveLeave(){this.SaveDesign().then(()=>{this.GoBack();},error=>this.Fail(error));},
  ...drawingTools,
  GoBack(){wx.disableAlertBeforeUnload();console.log('[开始] 指定返回目标');if(this.pendingNavigation){console.log('[分支] 继续先前导航');const navigate=this.pendingNavigation;this.pendingNavigation=null;navigate();console.log('[结束] 指定返回目标');return;}console.log('[分支] 返回前页；[结束] 指定返回目标');console.log('[开始] 返回目标');if(getCurrentPages().length>1){console.log('[分支] 上一页');wx.navigateBack();}else{console.log('[分支] 首页');wx.switchTab({url:'/pages/home/index'});}console.log('[结束] 返回目标');}
};
