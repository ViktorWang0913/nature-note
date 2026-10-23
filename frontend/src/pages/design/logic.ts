import notebook from '../canvas/logic';
import {request, operationId} from '../../services/api';
import {clone, History, fitViewport, screenToCanvas, attachAsset, uid} from '../../engine/scene';
import {Layout} from '../../types/models';

// 参数设置：独立设计复用笔记的渲染、手势、图片调整和历史记录。
export default {
  ...notebook,
  data:{...notebook.data,manual:true,title:'未命名自然笔记',assetSource:'all',backgroundColor:'#ffffff',layers:[],selectedLocked:false},
  createOperationId:'',
  canvasObserver:null as ResizeObserver|null,
  pendingCanvasResize:false,
  async Initialize(options:any){
    this.images=new Map();this.createOperationId=operationId();
    console.log('[开始] 手动设计初始化');
    if(options.projectId){
      console.log('[分支] 读取已有设计');
      const project=await request('/projects/'+options.projectId);
      console.log('[开始] 作品模式检查');
      if(project.layout.designMode!=='manual'){
        console.log('[分支] 返回观察笔记；[结束] 作品模式检查；[结束] 手动设计初始化，提前结束');
        wx.redirectTo({url:'/pages/canvas/index?projectId='+project.id});return;
      }
      console.log('[分支] 手动设计；[结束] 作品模式检查');
      this.layout=project.layout;this.setData({projectId:project.id,title:project.title,projectVersion:project.version});
    }else{
      console.log('[分支] 在本页建立空白画板，保存时才创建作品');
      this.layout={schema_version:1,notebookVersion:1,designMode:'manual',width:1024,height:1536,background:'#ffffff',elements:[]} as Layout;
    }
    console.log('[结束] 手动设计初始化');
    this.history=new History(this.layout!);this.savedSignature=this.Signature();
    this.setData({hasBackground:true,loading:true,backgroundColor:this.layout.background});
    this.UpdateDirty();await this.SetupCanvas();
    this.canvasObserver=new ResizeObserver(()=>this.ScheduleCanvas());this.canvasObserver.observe(this.canvas);
    console.log('[开始] 桌面素材侧栏');
    if(window.innerWidth>=900){console.log('[分支] 展开素材');this.Materials();}
    else{console.log('[分支] 手机按需打开素材');}
    console.log('[结束] 桌面素材侧栏');
    this.setData({loading:false});
  },
  onShow(){},
  onUnload(){this.canvasObserver?.disconnect();notebook.onUnload.call(this);},
  ScheduleCanvas(){
    clearTimeout(this.resizeTimer);
    this.resizeTimer=setTimeout(()=>{
      console.log('[开始] 手动画板尺寸适配');
      if(this.gesture||this.drawingGesture||this.manipulation){console.log('[分支] 等待当前手势结束');this.pendingCanvasResize=true;}
      else if(this.data.hasBackground&&!this.unloaded){
        console.log('[分支] 工具栏或侧栏尺寸已稳定');this.pendingCanvasResize=false;
        this.SetupCanvas().then(undefined,error=>this.Fail(error));
      }else{console.log('[分支] 页面尚未就绪或已关闭');}
      console.log('[结束] 手动画板尺寸适配');
    },220);
  },
  TouchEnd(event?:any){
    notebook.TouchEnd.call(this,event);
    console.log('[开始] 手势后的尺寸适配');
    if(this.pendingCanvasResize&&!this.gesture){console.log('[分支] 恢复画板适配');this.ScheduleCanvas();}
    else{console.log('[分支] 尺寸无待处理变化');}
    console.log('[结束] 手势后的尺寸适配');
  },
  Signature(){return JSON.stringify({title:this.data.title,layout:this.layout},(key,value)=>key==='url'?undefined:value);},
  TitleInput(event:any){this.setData({title:event.detail.value});this.UpdateDirty();},
  UpdateDirty(){
    notebook.UpdateDirty.call(this);

  },
  Select(id:string){notebook.Select.call(this,id);this.UpdateDirty();},
  Background(){this.OpenPaper();},
  Materials(){notebook.Materials.call(this);this.ScheduleCanvas();},
  async ExportImage(){await notebook.ExportImage.call(this);this.ScheduleCanvas();},
  Text(){
    console.log('[开始] 文字锁定检查');
    if(this.data.selectedLocked){console.log('[分支] 保留锁定文字，添加新文字');this.Select('');}
    else{console.log('[分支] 添加或编辑文字');}
    console.log('[结束] 文字锁定检查');notebook.Text.call(this);this.ScheduleCanvas();
  },
  PaperColor(event:any){const next=clone(this.layout!);next.background=event.detail.value;this.Commit(next);},
  Layers(){this.FinishDrawing();this.setData({panel:'layers'});this.ScheduleCanvas();},
  SelectLayer(event:any){this.Select(event.currentTarget.dataset.id);},
  LayerOrder(event:any){
    console.log('[开始] 图层排序选择');
    if(!this.data.selectedId||this.data.selectedLocked){console.log('[分支] 请先选择并解锁图层；[结束] 图层排序选择，提前结束');return;}
    console.log('[分支] 调整层叠；[结束] 图层排序选择');this.MoveLayer(Number(event.currentTarget.dataset.action));
  },
  ElementAction(event:any){notebook.ElementAction.call(this,event);},
  Zoom(event:any){
    const fit=fitViewport(this.layout!,this.canvasWidth,this.canvasHeight,12).scale;
    const zoom=Math.max(50,Math.min(600,this.data.zoom+Number(event.currentTarget.dataset.step)));
    const center={x:this.canvasWidth/2,y:this.canvasHeight/2},anchor=screenToCanvas(center,this.viewport),scale=fit*zoom/100;
    this.viewport={scale,x:center.x-anchor.x*scale,y:center.y-anchor.y*scale};this.setData({zoom});this.Draw();
  },
  DragAsset(event:any){event.nativeEvent.dataTransfer.setData('application/x-nature-asset',event.currentTarget.dataset.id);},
  DropAsset(event:any){this.InsertDroppedAsset(event).then(undefined,error=>this.Fail(error));},
  async InsertDroppedAsset(event:any){
    const rawEvent=event.nativeEvent,assetId=rawEvent.dataTransfer.getData('application/x-nature-asset');
    const asset=this.data.assets.find(item=>item.id===assetId);
    console.log('[开始] 拖入素材检查');
    if(!asset||this.data.busy){console.log('[分支] 忽略外部或未就绪素材；[结束] 拖入素材检查，提前结束');return;}
    console.log('[分支] 放置库内素材；[结束] 拖入素材检查');
    const bounds=this.canvas.getBoundingClientRect(),point=screenToCanvas({x:rawEvent.clientX-bounds.left,y:rawEvent.clientY-bounds.top},this.viewport);
    point.x=Math.max(0,Math.min(this.layout.width,point.x));point.y=Math.max(0,Math.min(this.layout.height,point.y));
    this.setData({busy:true});const next=attachAsset(this.layout,asset,point);this.Commit(next);await this.RefreshImages();
    this.setData({busy:false});this.Select(next.elements.at(-1).id);
  },
  async SaveDesign(){
    this.PrepareSave();
    console.log('[开始] 手动设计保存许可');
    if(this.data.busy||this.imageEditStart){console.log('[分支] 等待当前编辑；[结束] 手动设计保存许可，提前结束');return;}
    console.log('[分支] 保存完整作品；[结束] 手动设计保存许可');
    this.setData({busy:true,error:'',title:this.data.title.trim()||'未命名自然笔记'});
    const layout=clone(this.layout!),title=this.data.title;
    let response:any;
    console.log('[开始] 设计保存方式');
    if(this.data.projectId){
      console.log('[分支] 更新已有作品');response=await request('/projects/'+this.data.projectId,'PATCH',{base_version:this.data.projectVersion,title,layout});
    }else{
      console.log('[分支] 首次保存去重');response=await request('/projects','POST',{title,layout,operation_id:this.createOperationId});
      this.setData({projectId:response.id,projectVersion:response.version});
      console.log('[开始] 首次保存重试内容检查');
      const savedLayout=JSON.stringify(response.layout,(key,value)=>key==='url'?undefined:value);
      const currentLayout=JSON.stringify(layout,(key,value)=>key==='url'?undefined:value);
      if(response.title!==title||savedLayout!==currentLayout){
        console.log('[分支] 原创建已完成，保存重试前的新修改');
        response=await request('/projects/'+response.id,'PATCH',{base_version:response.version,title,layout});
      }else{console.log('[分支] 已保存当前设计');}
      console.log('[结束] 首次保存重试内容检查');
    }
    console.log('[结束] 设计保存方式');
    this.layout=response.layout;this.setData({projectId:response.id,title:response.title,projectVersion:response.version,busy:false});
    history.replaceState(history.state,'','#/pages/design/index?projectId='+response.id);
    this.savedSignature=this.Signature();this.UpdateDirty();
    await this.RefreshImages();wx.showToast({title:'已保存到我的笔记'});
  }
};
