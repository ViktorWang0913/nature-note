import type {SceneElement, ShapeKind} from '../types/models';

// 参数设置：路径采用局部归一化坐标，缩放后仍可编辑。
export const shapeChoices:{kind:ShapeKind;label:string;path:string}[]=[
  {kind:'rectangle',label:'矩形',path:'M2 6H30V26H2Z'},
  {kind:'square',label:'正方形',path:'M4 4H28V28H4Z'},
  {kind:'rounded',label:'圆角矩形',path:'M8 4H24Q28 4 28 8V24Q28 28 24 28H8Q4 28 4 24V8Q4 4 8 4Z'},
  {kind:'circle',label:'圆形',path:'M16 3A13 13 0 1 1 15.99 3Z'},
  {kind:'ellipse',label:'椭圆',path:'M16 6A14 10 0 1 1 15.99 6Z'},
  {kind:'triangle',label:'正三角形',path:'M16 3 30 28H2Z'},
  {kind:'triangleDown',label:'倒三角形',path:'M2 4H30L16 29Z'},
  {kind:'diamond',label:'菱形',path:'M16 2 30 16 16 30 2 16Z'},
  {kind:'pentagon',label:'五边形',path:'M16 2 30 12 25 29H7L2 12Z'},
  {kind:'hexagon',label:'六边形',path:'M8 3H24L31 16 24 29H8L1 16Z'},
  {kind:'hexagonPoint',label:'竖向六边形',path:'M16 1 29 8V24L16 31 3 24V8Z'},
  {kind:'star',label:'五角星',path:'m16 1 4.5 10 11 1-8 8 2 11-9.5-5-9.5 5 2-11-8-8 11-1Z'},
  {kind:'line',label:'直线',path:'M3 25 29 7'},
  {kind:'arrow',label:'单向箭头',path:'M3 25 29 7M17 7H29V19'},
  {kind:'doubleArrow',label:'双向箭头',path:'M3 25 29 7M17 7H29V19M3 13V25H15'}
];
export function IsLine(element:SceneElement){return ['line','arrow','doubleArrow'].includes(element.shape?.kind);}
export function ShapeLabel(kind:string){return shapeChoices.find(item=>item.kind===kind)?.label||'图形';}
export function DistanceToSegment(point:{x:number;y:number},first:{x:number;y:number},second:{x:number;y:number}){
  const dx=second.x-first.x,dy=second.y-first.y;
  const amount=Math.max(0,Math.min(1,((point.x-first.x)*dx+(point.y-first.y)*dy)/(dx*dx+dy*dy||1)));
  return Math.hypot(point.x-first.x-amount*dx,point.y-first.y-amount*dy);
}
export function StrokeScale(element:SceneElement){return Math.min(element.width/element.stroke.baseWidth,element.height/element.stroke.baseHeight);}
export function HitDrawing(element:SceneElement,point:{x:number;y:number},tolerance=10){
  const points=element.stroke?.points||element.shape?.points||[];
  const width=element.stroke?element.stroke.lineWidth*StrokeScale(element):element.shape?.lineWidth||1;
  console.log('[开始] 笔迹命中');
  for(let pointIndex=0;pointIndex<points.length;pointIndex++){
    console.log(`[开始] 线段 ${pointIndex+1}/${points.length}`);
    const first=points[Math.max(0,pointIndex-1)],second=points[pointIndex];
    const distance=DistanceToSegment(point,{x:first.x*element.width,y:first.y*element.height},{x:second.x*element.width,y:second.y*element.height});
    console.log('[开始] 距离判断');
    if(distance<=width/2+tolerance){console.log('[分支] 命中；[结束] 距离判断；[结束] 线段；[结束] 笔迹命中，提前结束');return true;}
    console.log('[分支] 未命中；[结束] 距离判断');console.log(`[结束] 线段 ${pointIndex+1}/${points.length}`);
  }
  console.log('[结束] 笔迹命中');return false;
}
export function BuildStroke(points:{x:number;y:number}[],lineWidth:number,color:string,opacity:number,id:string,z:number,brush:string):SceneElement{
  const padding=lineWidth/2+1;
  const left=Math.min(...points.map(point=>point.x))-padding,top=Math.min(...points.map(point=>point.y))-padding;
  const width=Math.max(...points.map(point=>point.x))-left+padding,height=Math.max(...points.map(point=>point.y))-top+padding;
  return {id,type:'stroke',x:left,y:top,width,height,rotation:0,z,opacity,
    stroke:{brush,color,lineWidth,baseWidth:width,baseHeight:height,points:points.map(point=>({x:(point.x-left)/width,y:(point.y-top)/height}))}};
}
export function DrawStroke(context:CanvasRenderingContext2D,element:SceneElement){
  const stroke=element.stroke,points=stroke.points;
  context.strokeStyle=stroke.color;context.fillStyle=stroke.color;context.lineWidth=stroke.lineWidth*StrokeScale(element);context.lineCap='round';context.lineJoin='round';
  context.beginPath();
  console.log('[开始] 点或笔画');
  if(points.length===1){console.log('[分支] 单点');context.arc(points[0].x*element.width,points[0].y*element.height,context.lineWidth/2,0,Math.PI*2);context.fill();}
  else{
    console.log('[分支] 平滑连续笔迹');context.moveTo(points[0].x*element.width,points[0].y*element.height);
    console.log('[开始] 笔迹曲线');
    for(let pointIndex=1;pointIndex<points.length;pointIndex++){
      console.log(`[开始] 曲线 ${pointIndex}/${points.length-1}`);
      const point=points[pointIndex],next=points[Math.min(pointIndex+1,points.length-1)];
      context.quadraticCurveTo(point.x*element.width,point.y*element.height,(point.x+next.x)*element.width/2,(point.y+next.y)*element.height/2);
      console.log(`[结束] 曲线 ${pointIndex}/${points.length-1}`);
    }
    console.log('[结束] 笔迹曲线');context.stroke();
  }
  console.log('[结束] 点或笔画');
}
function DrawArrow(context:CanvasRenderingContext2D,first:{x:number;y:number},last:{x:number;y:number},width:number){
  const angle=Math.atan2(last.y-first.y,last.x-first.x),size=Math.max(10,width*3);
  context.moveTo(last.x-Math.cos(angle-.45)*size,last.y-Math.sin(angle-.45)*size);context.lineTo(last.x,last.y);
  context.lineTo(last.x-Math.cos(angle+.45)*size,last.y-Math.sin(angle+.45)*size);
}
export function DrawShape(context:CanvasRenderingContext2D,element:SceneElement){
  const shape=element.shape,width=element.width,height=element.height;
  context.lineWidth=shape.lineWidth;context.strokeStyle=shape.stroke;context.fillStyle=shape.fill;context.lineJoin='round';context.lineCap='round';
  context.setLineDash(shape.dashed?[shape.lineWidth*3,shape.lineWidth*2]:[]);
  console.log('[开始] 标准图形绘制');
  if(IsLine(element)){
    console.log('[分支] 线段与箭头');const [first,last]=shape.points.map(point=>({x:point.x*width,y:point.y*height}));
    context.beginPath();context.moveTo(first.x,first.y);context.lineTo(last.x,last.y);context.stroke();context.setLineDash([]);context.beginPath();
    console.log('[开始] 箭头端点');
    if(shape.kind!=='line'){console.log('[分支] 结束端箭头');DrawArrow(context,first,last,shape.lineWidth);}else{console.log('[分支] 无箭头');}
    if(shape.kind==='doubleArrow'){console.log('[分支] 起始端箭头');DrawArrow(context,last,first,shape.lineWidth);}else{console.log('[分支] 无起始箭头');}
    console.log('[结束] 箭头端点');context.stroke();
  }else{
    console.log('[分支] 封闭图形');const path=new Path2D();
    console.log('[开始] 图形轮廓');
    if(shape.kind==='circle'||shape.kind==='ellipse'){console.log('[分支] 椭圆');path.ellipse(width/2,height/2,width/2,height/2,0,0,Math.PI*2);}
    else if(shape.kind==='rounded'){console.log('[分支] 圆角矩形');const radius=Math.min(width,height)*shape.radius/100;path.roundRect(0,0,width,height,radius);}
    else{console.log('[分支] 标准路径');const source=new Path2D(shapeChoices.find(item=>item.kind===shape.kind).path);path.addPath(source,new DOMMatrix().scale(width/32,height/32));}
    console.log('[结束] 图形轮廓');
    console.log('[开始] 填充与描边');
    if(shape.fill!=='none'){console.log('[分支] 填充');context.fill(path);}else{console.log('[分支] 无填充');}
    if(shape.stroke!=='none'){console.log('[分支] 描边');context.stroke(path);}else{console.log('[分支] 无描边');}
    console.log('[结束] 填充与描边');
  }
  console.log('[结束] 标准图形绘制');
}
