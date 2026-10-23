import {clone,uid,screenToCanvas,worldMatrix,inverse,transform,fitViewport} from '../../engine/scene';
import {BuildStroke,HitDrawing,IsLine,shapeChoices,ShapeLabel} from '../../engine/drawing';
import {HitControl} from '../../engine/notebook-controls';
import type {Layout,SceneElement,ShapeKind} from '../../types/models';

// 参数设置
export const drawingData={drawingMode:false,toolPanel:'',brushPopup:'',saveMenu:false,brushKind:'pen',brushColor:'#527c65',brushWidth:8,brushOpacity:100,
  brushPresets:{pen:{width:8,opacity:100},marker:{width:28,opacity:35},dot:{width:20,opacity:100},eraser:{width:16,opacity:100}},
  recentColors:[] as string[],shapeChoices,brushChoices:[{kind:'pen',label:'普通画笔',symbol:'✎'},{kind:'marker',label:'荧光笔',symbol:'▰'},{kind:'dot',label:'圆点笔',symbol:'●'},{kind:'eraser',label:'整笔擦除',symbol:'▱'}],
  styleForm:{opacity:100,color:'#527c65',fill:'#9eb594',stroke:'#416b55',lineWidth:3,dashed:false,radius:15,lockRatio:true},
  selectedLine:false,selectedShape:'',selectedLabel:'',canvasSize:'1024 × 1536',paperForm:{width:1024,height:1536,background:'#ffffff'},
  paperPresets:[{label:'原始 2:3',width:1024,height:1536},{label:'正方形',width:1080,height:1080},{label:'3:4',width:1080,height:1440},{label:'4:3',width:1440,height:1080},{label:'9:16',width:1080,height:1920},{label:'16:9',width:1920,height:1080}]};

// 自编函数：菜单、绘画与保存均复用同一份布局和撤销历史。
export default {
  drawingGesture:null as any,styleStart:null as Layout|null,manipulation:null as any,panOnly:false,
  SyncDrawingState(){
    const element=this.layout?.elements.find(item=>item.id===this.data.selectedId);
    this.setData({layers:[...(this.layout?.elements||[])].filter(item=>item.id!=='background').sort((first,second)=>second.z-first.z).map(item=>({...item,label:item.type==='shape'?ShapeLabel(item.shape.kind):item.type==='stroke'?'手绘笔画':item.type==='text'?item.text:'图片素材'})),
      selectedLocked:!!element?.locked,selectedLine:!!element&&IsLine(element),selectedShape:element?.shape?.kind||'',selectedLabel:element?.type==='shape'?ShapeLabel(element.shape.kind):({stroke:'笔画',image:'素材',text:'文字'}[element?.type]||''),canvasSize:this.layout?`${this.layout.width} × ${this.layout.height}`:'',
      styleForm:{opacity:Math.round((element?.opacity??1)*100),color:element?.stroke?.color||'#527c65',fill:element?.shape?.fill||'#9eb594',stroke:element?.shape?.stroke||'#416b55',lineWidth:element?.shape?.lineWidth||3,dashed:!!element?.shape?.dashed,radius:element?.shape?.radius??15,lockRatio:element?.shape?.lockRatio??true}});
  },
  PrepareSave(){
    this.TouchEnd();this.FinishStyle();this.setData({saveMenu:false});
    console.log('[开始] 保存编辑状态');
    if(this.imageEditStart||!this.layout||this.data.busy){console.log('[分支] 当前不可保存；[结束] 保存编辑状态，提前结束');throw new Error('请先完成当前编辑');}
    console.log('[分支] 保存当前完整画布；[结束] 保存编辑状态');
  },
  ToggleSaveMenu(){this.TouchEnd();this.setData({saveMenu:!this.data.saveMenu,toolPanel:'',brushPopup:''});},
  ToggleTool(event:any){
    const tool=event.currentTarget.dataset.tool;this.TouchEnd();this.ClosePanel();
    const opening=this.data.toolPanel!==tool;
    this.setData({toolPanel:opening?tool:'',brushPopup:'',saveMenu:false,drawingMode:tool==='brush'});this.Select('');
  },
  FinishDrawing(){this.TouchEnd();this.setData({drawingMode:false,toolPanel:'',brushPopup:'',saveMenu:false});},
  ChooseBrush(event:any){
    const brushKind=event.currentTarget.dataset.kind,settings=this.data.brushPresets[brushKind];
    this.setData({brushKind,brushWidth:settings.width,brushOpacity:settings.opacity,brushColor:settings.color||'#527c65',drawingMode:true});
  },
  BrushPopup(event:any){const popup=event.currentTarget.dataset.popup;this.setData({brushPopup:this.data.brushPopup===popup?'':popup});},
  BrushSetting(event:any){
    const field=event.currentTarget.dataset.field,value=Number(event.detail.value);
    console.log('[开始] 笔刷数值');
    if(!Number.isFinite(value)){console.log('[分支] 忽略无效输入；[结束] 笔刷数值，提前结束');return;}
    console.log('[分支] 限制到支持范围；[结束] 笔刷数值');
    const nextValue=Math.max(field==='brushWidth'?1:0,Math.min(field==='brushWidth'?80:100,value));
    const presets=clone(this.data.brushPresets);presets[this.data.brushKind][field==='brushWidth'?'width':'opacity']=nextValue;
    this.setData({[field]:nextValue,brushPresets:presets});
  },
  BrushColor(event:any){
    const color=event.currentTarget.dataset.color||event.detail.value;
    console.log('[开始] 画笔颜色');
    if(!/^#[\da-f]{6}$/i.test(color)){console.log('[分支] 请使用六位颜色值；[结束] 画笔颜色，提前结束');return;}
    console.log('[分支] 记录最近颜色；[结束] 画笔颜色');
    const presets=clone(this.data.brushPresets);presets[this.data.brushKind].color=color;
    this.setData({brushColor:color,brushPresets:presets,recentColors:[color,...this.data.recentColors.filter(item=>item!==color)].slice(0,8)});
  },
  DrawingPoint(touch:any){const point=screenToCanvas(touch,this.viewport);return {x:Math.max(0,Math.min(this.layout.width,point.x)),y:Math.max(0,Math.min(this.layout.height,point.y))};},
  TouchStart(event:any){
    console.log('[开始] 绘画输入');
    if(!this.layout||this.data.busy||this.data.panel==='image'||!event.touches.length){console.log('[分支] 暂不可操作；[结束] 绘画输入，提前结束');return;}
    this.setData({saveMenu:false,toolPanel:'',brushPopup:''});
    if(this.data.drawingMode){
      console.log('[分支] 绘画模式');
      console.log('[开始] 绘画手指数');
      if(event.touches.length>1){
        console.log('[分支] 撤销未完成笔迹，双指浏览画布');
        this.CancelStroke();this.panOnly=true;this.Select('');this.CanvasTouchStart(event);this.Draw();
      }else if(!this.panOnly){
        console.log('[分支] 新笔画');
        const point=screenToCanvas(event.touches[0],this.viewport);
        console.log('[开始] 起笔范围');
        if(point.x<0||point.y<0||point.x>this.layout.width||point.y>this.layout.height){console.log('[分支] 画布外不绘画；[结束] 起笔范围；[结束] 绘画手指数；[结束] 绘画输入，提前结束');return;}
        if(this.layout.elements.length>=200&&this.data.brushKind!=='eraser'){console.log('[分支] 图层已满；[结束] 起笔范围；[结束] 绘画手指数；[结束] 绘画输入，提前结束');this.setData({error:'图层已达 200 个，请先删除部分图层'});return;}
        console.log('[分支] 画布内；[结束] 起笔范围');
        this.drawingGesture={before:clone(this.layout),points:[point],id:uid('stroke'),z:Math.max(0,...this.layout.elements.map(item=>item.z))+1};this.PreviewStroke(point);
      }else{console.log('[分支] 等待所有手指抬起');}
      console.log('[结束] 绘画手指数');
    }else{
      console.log('[分支] 普通元素编辑');
      console.log('[开始] 特殊控制点');
      if(!this.StartManipulation(event)){console.log('[分支] 常规拖动');this.CanvasTouchStart(event);}else{console.log('[分支] 端点或自由尺寸');}
      console.log('[结束] 特殊控制点');
    }
    console.log('[结束] 绘画输入');
  },
  PreviewStroke(point:any){
    const session=this.drawingGesture;
    console.log('[开始] 笔迹预览');
    if(this.data.brushKind==='eraser'){
      console.log('[分支] 仅擦除可编辑笔画');
      const next=clone(this.layout);next.elements=next.elements.filter(element=>{
        console.log('[开始] 擦除对象判断');
        if(element.type!=='stroke'||element.locked){console.log('[分支] 保留其他或锁定内容；[结束] 擦除对象判断，提前结束');return true;}
        const local=transform(inverse(worldMatrix(next,element)),point);local.x=element.flipX?element.width-local.x:local.x;local.y=element.flipY?element.height-local.y:local.y;
        console.log('[分支] 按笔迹检测；[结束] 擦除对象判断');return !HitDrawing(element,local,12/this.viewport.scale);
      });this.layout=next;
    }else{
      console.log('[分支] 归一化单笔路径');
      const next=clone(session.before);next.elements.push(BuildStroke(session.points,this.data.brushWidth,this.data.brushColor,this.data.brushOpacity/100,session.id,session.z,this.data.brushKind));this.layout=next;
    }
    console.log('[结束] 笔迹预览');this.Draw();
  },
  TouchMove(event:any){
    console.log('[开始] 编辑移动');
    if(this.manipulation){console.log('[分支] 移动控制点');this.MoveManipulation(event);}
    else if(this.drawingGesture&&event.touches.length===1){
      console.log('[分支] 采样笔画');const session=this.drawingGesture,point=this.DrawingPoint(event.touches[0]),previous=session.points.at(-1);
      console.log('[开始] 笔迹采样距离');
      if(this.data.brushKind!=='dot'&&session.points.length<2048&&Math.hypot(point.x-previous.x,point.y-previous.y)>=Math.max(1,1/this.viewport.scale)){console.log('[分支] 添加轨迹点');session.points.push(point);this.PreviewStroke(point);}
      else{console.log('[分支] 圆点、相近采样或达到单笔长度限制');}
      console.log('[结束] 笔迹采样距离');
    }else{console.log('[分支] 浏览或移动元素');this.CanvasTouchMove(event);}
    console.log('[结束] 编辑移动');
  },
  CancelStroke(){
    console.log('[开始] 取消当前笔画');
    if(this.drawingGesture){console.log('[分支] 恢复起笔前画布');this.layout=this.drawingGesture.before;this.drawingGesture=null;this.Draw();}
    else{console.log('[分支] 无当前笔画');}
    console.log('[结束] 取消当前笔画');
  },
  TouchEnd(event?:any){
    console.log('[开始] 完成编辑手势');
    if(event?.nativeEvent?.type==='pointercancel'){console.log('[分支] 系统取消笔迹');this.CancelStroke();this.layout=this.manipulation?.before||this.layout;this.manipulation=null;this.gesture=null;this.panOnly=false;this.Draw();}
    else if(this.drawingGesture){console.log('[分支] 一笔一次撤销');this.drawingGesture=null;this.Commit(this.layout);}
    else if(this.manipulation){console.log('[分支] 记录控制点变更');this.manipulation=null;this.Commit(this.layout);}
    else if(this.panOnly){
      console.log('[分支] 浏览结束');this.gesture=null;
      console.log('[开始] 剩余浏览手指');
      if(event?.touches?.length){console.log('[分支] 保持浏览');this.CanvasTouchStart(event);}else{console.log('[分支] 恢复绘画');this.panOnly=false;}
      console.log('[结束] 剩余浏览手指');
    }else{console.log('[分支] 普通手势结束');this.CanvasTouchEnd(event);}
    console.log('[结束] 完成编辑手势');
  },
  StartManipulation(event:any){
    const element=this.layout.elements.find(item=>item.id===this.data.selectedId);
    console.log('[开始] 特殊图层控制');
    if(!element?.shape||element.locked||event.touches.length!==1){console.log('[分支] 不适用；[结束] 特殊图层控制，提前结束');return false;}
    const point=screenToCanvas(event.touches[0],this.viewport),matrix=worldMatrix(this.layout,element),local=transform(inverse(matrix),point);
    const control=HitControl(this.layout,element,point,this.viewport,{width:this.canvasWidth,height:this.canvasHeight});
    if(control==='move'||control==='rotate'){console.log('[分支] 独立移动或旋转；[结束] 特殊图层控制，提前结束');return false;}
    const endpoint=IsLine(element)?element.shape.points.findIndex(item=>Math.hypot(local.x-(element.flipX?1-item.x:item.x)*element.width,local.y-(element.flipY?1-item.y:item.y)*element.height)*this.viewport.scale<16):-1;
    const freeScale=!element.shape.lockRatio&&control==='scale';
    if(endpoint<0&&!freeScale){console.log('[分支] 普通控制；[结束] 特殊图层控制，提前结束');return false;}
    console.log('[分支] 开始端点或非等比缩放；[结束] 特殊图层控制');
    this.manipulation={before:clone(this.layout),id:element.id,endpoint,start:local,corner:{x:local.x<element.width/2?0:element.width,y:local.y<element.height/2?0:element.height},anchor:{x:local.x<element.width/2?element.width:0,y:local.y<element.height/2?element.height:0}};return true;
  },
  MoveManipulation(event:any){
    console.log('[开始] 控制点移动');
    if(event.touches.length!==1){console.log('[分支] 等待单指；[结束] 控制点移动，提前结束');return;}
    const session=this.manipulation,next=clone(session.before),element=next.elements.find(item=>item.id===session.id),matrix=worldMatrix(next,element),point=screenToCanvas(event.touches[0],this.viewport);
    if(session.endpoint>=0){
      console.log('[分支] 移动线条端点');const endpoints=element.shape.points.map(item=>transform(matrix,{x:(element.flipX?1-item.x:item.x)*element.width,y:(element.flipY?1-item.y:item.y)*element.height}));endpoints[session.endpoint]=point;
      element.x=Math.min(...endpoints.map(item=>item.x));element.y=Math.min(...endpoints.map(item=>item.y));element.width=Math.max(1,Math.abs(endpoints[1].x-endpoints[0].x));element.height=Math.max(1,Math.abs(endpoints[1].y-endpoints[0].y));element.rotation=0;element.flipX=false;element.flipY=false;
      element.shape.points=endpoints.map(item=>({x:(item.x-element.x)/element.width,y:(item.y-element.y)/element.height}));
    }else{
      console.log('[分支] 自由缩放');const moved=transform(inverse(matrix),point),anchor=session.anchor;
      const local={x:session.corner.x+moved.x-session.start.x,y:session.corner.y+moved.y-session.start.y};
      const width=Math.max(16,Math.min(5000,Math.abs(local.x-anchor.x))),height=Math.max(16,Math.min(5000,Math.abs(local.y-anchor.y)));
      const center=transform(matrix,{x:anchor.x+Math.sign(local.x-anchor.x)*width/2,y:anchor.y+Math.sign(local.y-anchor.y)*height/2});
      element.width=width;element.height=height;element.x=center.x-width/2;element.y=center.y-height/2;
    }
    console.log('[结束] 控制点移动');this.layout=next;this.Draw();
  },
  AddShape(event:any){
    this.FinishDrawing();const next=clone(this.layout),kind=event.currentTarget.dataset.kind as ShapeKind;
    console.log('[开始] 添加图形许可');
    if(next.elements.length>=200){console.log('[分支] 图层已满；[结束] 添加图形许可，提前结束');throw new Error('图层已达 200 个，请先删除部分图层');}
    console.log('[分支] 添加标准图形；[结束] 添加图形许可');
    const width=Math.min(next.width,next.height)*.23,height=['rectangle','rounded','ellipse'].includes(kind)?width*.65:width;
    const point=screenToCanvas({x:this.canvasWidth/2,y:this.canvasHeight/2},this.viewport);
    const element:SceneElement={id:uid('shape'),type:'shape',x:Math.max(0,Math.min(next.width-width,point.x-width/2)),y:Math.max(0,Math.min(next.height-height,point.y-height/2)),width,height,rotation:0,z:Math.max(0,...next.elements.map(item=>item.z))+1,opacity:1,
      shape:{kind,fill:'#9eb594',stroke:'#416b55',lineWidth:3,dashed:false,radius:15,lockRatio:true,points:[{x:0,y:.5},{x:1,y:.5}]}};
    next.elements.push(element);this.Commit(next);this.Select(element.id);
  },
  OpenStyle(){this.FinishDrawing();this.styleStart=null;this.setData({panel:'style'});this.ScheduleCanvas();},
  StyleInput(event:any){
    const element=this.layout.elements.find(item=>item.id===this.data.selectedId);
    console.log('[开始] 图层样式许可');
    if(!element||element.locked||this.data.busy){console.log('[分支] 不可编辑；[结束] 图层样式许可，提前结束');return;}
    console.log('[分支] 预览样式；[结束] 图层样式许可');this.styleStart=this.styleStart||clone(this.layout);
    const field=event.currentTarget.dataset.field,raw=event.currentTarget.dataset.value??event.detail.value;
    const value=['opacity','lineWidth','radius'].includes(field)?Number(raw):raw;
    console.log('[开始] 样式数值范围');
    if(['opacity','lineWidth','radius'].includes(field)&&(!Number.isFinite(value)||value<(field==='lineWidth'?1:0)||value>({opacity:100,lineWidth:40,radius:50}[field]))){console.log('[分支] 数值超出范围；[结束] 样式数值范围，提前结束');this.setData({error:'不透明度为 0–100%，描边为 1–40 px，圆角为 0–50%'});return;}
    console.log('[分支] 有效输入；[结束] 样式数值范围');
    console.log('[开始] 样式字段');
    if(field==='opacity'){console.log('[分支] 通用透明度');element.opacity=Math.max(0,Math.min(100,value))/100;}
    else if(field==='color'&&element.stroke){console.log('[分支] 笔画颜色');element.stroke.color=value;}
    else if(element.shape){
      console.log('[分支] 图形样式');const shape={...element.shape,[field]:value};
      console.log('[开始] 可见样式检查');
      if((shape.fill==='none'&&shape.stroke==='none')||(IsLine(element)&&shape.stroke==='none')){console.log('[分支] 至少保留一种颜色；[结束] 可见样式检查；[结束] 样式字段，提前结束');this.setData({error:'填充和描边不能同时为空，线条必须有描边'});return;}
      console.log('[分支] 样式有效；[结束] 可见样式检查');element.shape=shape;
    }else{console.log('[分支] 未适用字段');}
    console.log('[结束] 样式字段');this.UpdateDirty();this.Draw();
  },
  FinishStyle(){console.log('[开始] 样式撤销记录');if(this.styleStart){console.log('[分支] 提交一次样式调整');this.styleStart=null;this.Commit(this.layout);}else{console.log('[分支] 无样式预览');}console.log('[结束] 样式撤销记录');},
  ApplyStyle(event:any){this.StyleInput(event);this.FinishStyle();},
  OpenPaper(){this.FinishDrawing();this.setData({panel:'paper',paperForm:{width:this.layout.width,height:this.layout.height,background:this.layout.background}});this.ScheduleCanvas();},
  PaperInput(event:any){const field=event.currentTarget.dataset.field;this.setData({paperForm:{...this.data.paperForm,[field]:field==='background'?event.detail.value:Number(event.detail.value)}});},
  PaperPreset(event:any){const preset=this.data.paperPresets[Number(event.currentTarget.dataset.index)];this.setData({paperForm:{...this.data.paperForm,width:preset.width,height:preset.height}});},
  SwapPaper(){this.setData({paperForm:{...this.data.paperForm,width:this.data.paperForm.height,height:this.data.paperForm.width}});},
  async ApplyPaper(){
    const form=this.data.paperForm,next=clone(this.layout),width=this.data.manual?Number(form.width):next.width,height=this.data.manual?Number(form.height):next.height;
    console.log('[开始] 画布设置检查');
    if(!Number.isInteger(width)||!Number.isInteger(height)||width<100||height<100||width>4096||height>4096){console.log('[分支] 尺寸无效；[结束] 画布设置检查，提前结束');throw new Error('宽高须为 100–4096 的整数像素');}
    console.log('[分支] 尺寸有效；[结束] 画布设置检查');
    const dx=(width-next.width)/2,dy=(height-next.height)/2;
    console.log('[开始] 画布元素平移');
    next.elements.forEach((element,index)=>{console.log(`[开始] 元素 ${index+1}/${next.elements.length}`);element.x+=dx;element.y+=dy;console.log(`[结束] 元素 ${index+1}/${next.elements.length}`);});
    console.log('[结束] 画布元素平移');
    const outside=next.elements.some(element=>{const matrix=worldMatrix(next,element);return [{x:0,y:0},{x:element.width,y:0},{x:0,y:element.height},{x:element.width,y:element.height}].some(point=>{const world=transform(matrix,point);return world.x<0||world.y<0||world.x>width||world.y>height;});});
    console.log('[开始] 尺寸裁切确认');
    if(outside&&(dx||dy)){
      console.log('[分支] 提醒保留画布外内容');const answer:any=await new Promise(resolve=>wx.showModal({title:'部分内容将超出画布',content:'超出部分仍保留在作品中，导出时会被裁切。可从图层中选择并移回，或撤销本次尺寸调整。',success:resolve}));
      console.log('[开始] 裁切选择');if(!answer.confirm){console.log('[分支] 已取消；[结束] 裁切选择；[结束] 尺寸裁切确认，提前结束');return;}console.log('[分支] 已确认；[结束] 裁切选择');
    }else{console.log('[分支] 无新增裁切');}
    console.log('[结束] 尺寸裁切确认');next.width=width;next.height=height;next.background=form.background;this.Commit(next);this.ClosePanel();this.Fit();
  },
  SaveAndExport(){this.SaveDesign().then(()=>this.ExportImage()).then(undefined,error=>this.Fail(error));},
  Layers(){this.FinishDrawing();this.setData({panel:'layers'});this.ScheduleCanvas();},
  SelectLayer(event:any){this.Select(event.currentTarget.dataset.id);},
  LayerOrder(event:any){console.log('[开始] 图层排序许可');if(!this.data.selectedId||this.data.selectedLocked){console.log('[分支] 请先选择并解锁；[结束] 图层排序许可，提前结束');return;}console.log('[分支] 排序；[结束] 图层排序许可');this.MoveLayer(Number(event.currentTarget.dataset.action));},
  ElementAction(event:any){
    const action=event.currentTarget.dataset.action,next=clone(this.layout),element=next.elements.find(item=>item.id===this.data.selectedId);
    console.log('[开始] 通用图层操作');
    if(!element||this.data.busy||(element.locked&&action!=='lock')){console.log('[分支] 当前不可编辑；[结束] 通用图层操作，提前结束');return;}
    if(action==='duplicate'){console.log('[分支] 复制');if(next.elements.length>=200){console.log('[分支] 图层已满；[结束] 通用图层操作，提前结束');throw new Error('图层已达 200 个');}const copied={...clone(element),id:uid('copy'),x:element.x+24,y:element.y+24,z:Math.max(0,...next.elements.map(item=>item.z))+1};next.elements.push(copied);this.Commit(next);this.Select(copied.id);}
    else if(action==='lock'){console.log('[分支] 锁定');element.locked=!element.locked;this.Commit(next);}
    else if(action==='centerX'||action==='centerY'){console.log('[分支] 居中');element[action==='centerX'?'x':'y']=action==='centerX'?(next.width-element.width)/2:(next.height-element.height)/2;this.Commit(next);}
    else if(action==='flipX'||action==='flipY'){console.log('[分支] 翻转');element[action]=!element[action];this.Commit(next);}
    else{console.log('[分支] 未知操作');}
    console.log('[结束] 通用图层操作');
  },
  Zoom(event:any){const fit=fitViewport(this.layout,this.canvasWidth,this.canvasHeight,12).scale,zoom=Math.max(50,Math.min(600,this.data.zoom+Number(event.currentTarget.dataset.step)));const center={x:this.canvasWidth/2,y:this.canvasHeight/2},anchor=screenToCanvas(center,this.viewport),scale=fit*zoom/100;this.viewport={scale,x:center.x-anchor.x*scale,y:center.y-anchor.y*scale};this.setData({zoom});this.Draw();}
};
