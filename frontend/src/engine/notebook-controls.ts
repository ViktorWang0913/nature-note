import {Layout, SceneElement} from '../types/models';
import {Point, Viewport, inverse, worldMatrix, transform} from './scene';

// 参数设置：操作柄大小固定，移动柄的触摸直径为 44 像素。
const handleRadius=12;
export interface ControlSize {width:number;height:number}
export function ControlGeometry(layout:Layout,element:SceneElement,viewport:Viewport,size:ControlSize={width:Infinity,height:Infinity}){
  const paddingX=Math.max(0,(48/viewport.scale-element.width)/2),paddingY=Math.max(0,(48/viewport.scale-element.height)/2);
  const corners=[{x:-paddingX,y:-paddingY},{x:element.width+paddingX,y:-paddingY},{x:-paddingX,y:element.height+paddingY},{x:element.width+paddingX,y:element.height+paddingY}];
  const rotate={x:element.width/2,y:-paddingY-32/viewport.scale},matrix=worldMatrix(layout,element);
  console.log('[开始] 控制柄屏幕位置');
  const screenPoints=[...corners,rotate].map((point,index)=>{
    console.log(`[开始] 控制柄 ${index+1}/5`);const world=transform(matrix,point);
    const screen={x:viewport.x+world.x*viewport.scale,y:viewport.y+world.y*viewport.scale};
    console.log(`[结束] 控制柄 ${index+1}/5`);return screen;
  });
  console.log('[结束] 控制柄屏幕位置');
  const left=Math.min(...screenPoints.map(point=>point.x)),right=Math.max(...screenPoints.map(point=>point.x));
  const top=Math.min(...screenPoints.map(point=>point.y)),bottom=Math.max(...screenPoints.map(point=>point.y));
  const center={x:(left+right)/2,y:(top+bottom)/2};
  const candidates=[{x:right+44,y:center.y},{x:left-44,y:center.y},{x:center.x,y:bottom+44},{x:center.x,y:top-44}];
  console.log('[开始] 移动柄边缘避让');
  const placements=candidates.map((point,index)=>{
    console.log(`[开始] 方向 ${index+1}/4`);
    const position={x:Math.max(24,Math.min(size.width-24,point.x)),y:Math.max(24,Math.min(size.height-24,point.y))};
    const clearance=Math.min(...screenPoints.map(control=>Math.hypot(control.x-position.x,control.y-position.y)));
    const score=Math.min(44,clearance)-Math.hypot(position.x-point.x,position.y-point.y);
    console.log(`[结束] 方向 ${index+1}/4`);return {position,score};
  });
  console.log('[结束] 移动柄边缘避让');
  const moveScreen=placements.sort((first,second)=>second.score-first.score)[0].position;
  const move=transform(inverse(matrix),{x:(moveScreen.x-viewport.x)/viewport.scale,y:(moveScreen.y-viewport.y)/viewport.scale});
  return {corners,rotate,move,moveScreen};
}
export function HitControl(layout:Layout,element:SceneElement,point:Point,viewport:Viewport,size?:ControlSize):'move'|'scale'|'rotate'|'' {
  console.log('[开始] 控制柄命中');
  if(element.locked){console.log('[分支] 图层锁定；[结束] 控制柄命中，提前结束');return '';}
  const localPoint=transform(inverse(worldMatrix(layout,element)),point),controls=ControlGeometry(layout,element,viewport,size);
  if(Math.hypot(localPoint.x-controls.move.x,localPoint.y-controls.move.y)*viewport.scale<=22){console.log('[分支] 独立移动；[结束] 控制柄命中，提前结束');return 'move';}
  if(Math.hypot(localPoint.x-controls.rotate.x,localPoint.y-controls.rotate.y)*viewport.scale<=handleRadius){console.log('[分支] 旋转；[结束] 控制柄命中，提前结束');return 'rotate';}
  const distance=Math.min(...controls.corners.map(corner=>Math.hypot(localPoint.x-corner.x,localPoint.y-corner.y)*viewport.scale));
  if(distance<=handleRadius){console.log('[分支] 缩放；[结束] 控制柄命中，提前结束');return 'scale';}
  console.log('[分支] 对象主体或空白；[结束] 控制柄命中');return '';
}
