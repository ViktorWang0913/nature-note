import {CachedImage} from '../web/media';

import { Layout, SceneElement } from '../types/models';
import { Point, Viewport, worldMatrix, transform } from './scene';
import {DrawStroke,DrawShape,IsLine} from './drawing';
import {ControlGeometry,ControlSize} from './notebook-controls';
import {AdjustImage} from './image-adjustment';


export interface RenderOptions { viewport?:Viewport; selectedId?:string; selectedNode?:string; clear?:boolean; controlSize?:ControlSize }
async function ImageSource(element:SceneElement):Promise<string>{return CachedImage(element.url!,element.asset_id||element.id);}
export async function loadImages(canvas:any,layout:Layout,previous=new Map<string,any>()):Promise<Map<string,any>> {
  const loaded=new Map<string,any>();const elements=Array.from(new Map(layout.elements.filter(e=>e.type==='image'&&e.url).map(e=>[e.url!,e])).values());
  console.log('[开始] 画布图片加载');
  await Promise.all(elements.map(async (element,imageIndex)=>{
    console.log(`[开始] 图片 ${imageIndex+1}/${elements.length}`);
    const cached=previous.get(element.url!);
    console.log('[开始] 已解码图片检查');
    if(cached){
      console.log('[分支] 复用原尺寸图片');loaded.set(element.url!,cached);
    }else{
      console.log('[分支] 仅加载新增图片');
      const source=await ImageSource(element);
      await new Promise<void>((resolve,reject)=>{
        const picture=canvas.createImage();
        picture.onload=()=>{URL.revokeObjectURL(source);loaded.set(element.url!,picture);resolve();};
        picture.onerror=()=>{URL.revokeObjectURL(source);reject(new Error('素材加载失败，请检查网络后重试'));};
        picture.src=source;
      });
    }
    console.log('[结束] 已解码图片检查');console.log(`[结束] 图片 ${imageIndex+1}/${elements.length}`);
  }));
  console.log('[结束] 画布图片加载');return loaded;
}
function line(ctx:any,points:Point[],smooth:boolean){
  if(!points.length)return;ctx.moveTo(points[0].x,points[0].y);
  if(smooth&&points.length>2){for(let i=1;i<points.length-1;i++){const p=points[i],q=points[i+1];ctx.quadraticCurveTo(p.x,p.y,(p.x+q.x)/2,(p.y+q.y)/2);}const p=points[points.length-1];ctx.lineTo(p.x,p.y);}
  else for(let i=1;i<points.length;i++){const a=points[i-1],b=points[i];if(!smooth){ctx.lineTo(b.x,a.y);}ctx.lineTo(b.x,b.y);}
}
function route(ctx:any,el:SceneElement){
  const r=el.route!;ctx.lineWidth=r.lineWidth||36;ctx.strokeStyle=r.color||'#bebbb6';ctx.lineJoin='round';ctx.lineCap='round';
  const segments=(r as any).segments as Point[][]|undefined;for(const pts of segments||[r.points]){if(pts.length<2)continue;ctx.beginPath();line(ctx,pts,r.style==='smooth');ctx.stroke();}
  for(const n of r.nodes){ctx.beginPath();ctx.arc(n.x,n.y,Math.max(30,el.width*.018),0,Math.PI*2);ctx.fillStyle='#63ac77';ctx.fill();ctx.lineWidth=8;ctx.strokeStyle='#ffffff';ctx.stroke();ctx.fillStyle='#fff';ctx.textAlign='center';ctx.textBaseline='middle';ctx.font=`bold ${Math.max(26,el.width*.016)}px sans-serif`;ctx.fillText(n.label,n.x,n.y);}
}
function DrawText(ctx:any,el:SceneElement){
  const size=el.fontSize||42,alignment=el.textAlign||'left';
  ctx.save();ctx.beginPath();ctx.rect(0,0,el.width,el.height);ctx.clip();
  ctx.fillStyle=el.textBackground||'transparent';ctx.fillRect(0,0,el.width,el.height);
  ctx.font=`${el.fontWeight||'normal'} ${size}px ${el.fontFamily||'sans-serif'}`;
  ctx.fillStyle=el.color||'#253d32';ctx.textAlign=alignment;ctx.textBaseline='top';
  const offset={left:0,center:el.width/2,right:el.width}[alignment];
  let lineText='',lineY=0;
  const characters=Array.from(el.text||'');
  console.log('[开始] 文字排版，共 '+characters.length+' 字');
  characters.forEach((character,index)=>{
    console.log('[开始] 排字 '+(index+1)+'/'+characters.length);
    console.log('[开始] 换行判断');
    if(character==='\n'||(lineText&&ctx.measureText(lineText+character).width>el.width)){
      console.log('[分支] 输出当前行');ctx.fillText(lineText,offset,lineY);lineY+=size*1.45;lineText='';
    }else{console.log('[分支] 保持当前行');}
    console.log('[结束] 换行判断');
    lineText+=character.replace('\n','');
    console.log('[结束] 排字 '+(index+1)+'/'+characters.length);
  });
  console.log('[结束] 文字排版');ctx.fillText(lineText,offset,lineY);ctx.restore();
}
export function renderScene(ctx:any,layout:Layout,images:Map<string,any>,options:RenderOptions={}){
  const v=options.viewport||{x:0,y:0,scale:1};ctx.save();ctx.translate(v.x,v.y);ctx.scale(v.scale,v.scale);ctx.fillStyle=layout.background;ctx.fillRect(0,0,layout.width,layout.height);
  ctx.save();ctx.beginPath();ctx.rect(0,0,layout.width,layout.height);ctx.clip();
  for(const el of [...layout.elements].sort((a,b)=>a.z-b.z)){
    ctx.save();const m=worldMatrix(layout,el);ctx.transform(...m);
    console.log('[开始] 元素翻转绘制');
    if(el.flipX||el.flipY){console.log('[分支] 围绕元素中心翻转');ctx.translate(el.width/2,el.height/2);ctx.scale(el.flipX?-1:1,el.flipY?-1:1);ctx.translate(-el.width/2,-el.height/2);}
    else{console.log('[分支] 原始方向');}
    console.log('[结束] 元素翻转绘制');
    ctx.globalAlpha=el.opacity??1;
    if(el.type==='stroke')DrawStroke(ctx,el);
    if(el.type==='shape')DrawShape(ctx,el);
    if(el.type==='image'){const source=images.get(el.url||'');if(source){const img=el.imageEdit?AdjustImage(source,el.imageEdit):source;const ratio=Math.min(el.width/img.width,el.height/img.height),w=img.width*ratio,h=img.height*ratio;ctx.drawImage(img,(el.width-w)/2,(el.height-h)/2,w,h);}}
    if(el.type==='text')DrawText(ctx,el);if(el.type==='route'&&el.route)route(ctx,el);ctx.restore();
  }ctx.restore();
  const selectedElement=layout.elements.find(element=>element.id===options.selectedId);
  console.log('[开始] 选中对象控制柄');
  if(selectedElement&&!selectedElement.locked){
    console.log('[分支] 显示缩放、旋转与独立移动');
    const controls=ControlGeometry(layout,selectedElement,v,options.controlSize);
    ctx.save();ctx.transform(...worldMatrix(layout,selectedElement));ctx.lineWidth=2/v.scale;ctx.strokeStyle='#ff6b2c';
    ctx.strokeRect(0,0,selectedElement.width,selectedElement.height);
    console.log('[开始] 缩放控制点');
    controls.corners.forEach((point,index)=>{console.log(`[开始] 角点 ${index+1}/4`);ctx.beginPath();ctx.arc(point.x,point.y,5/v.scale,0,Math.PI*2);ctx.fillStyle='#fff';ctx.fill();ctx.stroke();console.log(`[结束] 角点 ${index+1}/4`);});
    console.log('[结束] 缩放控制点');
    ctx.beginPath();ctx.moveTo(selectedElement.width/2,0);ctx.lineTo(controls.rotate.x,controls.rotate.y);ctx.stroke();
    ctx.beginPath();ctx.arc(controls.rotate.x,controls.rotate.y,7/v.scale,0,Math.PI*2);ctx.fillStyle='#ff6b2c';ctx.fill();ctx.restore();
    // 屏幕坐标中的四向箭头不随图形旋转或画布缩放改变大小。
    ctx.save();ctx.translate((controls.moveScreen.x-v.x)/v.scale,(controls.moveScreen.y-v.y)/v.scale);ctx.scale(1/v.scale,1/v.scale);
    ctx.beginPath();ctx.arc(0,0,16,0,Math.PI*2);ctx.fillStyle='#ffffff';ctx.fill();ctx.strokeStyle='#38634f';ctx.lineWidth=1.5;ctx.stroke();
    ctx.beginPath();ctx.moveTo(-9,0);ctx.lineTo(9,0);ctx.moveTo(0,-9);ctx.lineTo(0,9);
    ctx.moveTo(-5,-4);ctx.lineTo(-9,0);ctx.lineTo(-5,4);ctx.moveTo(5,-4);ctx.lineTo(9,0);ctx.lineTo(5,4);
    ctx.moveTo(-4,-5);ctx.lineTo(0,-9);ctx.lineTo(4,-5);ctx.moveTo(-4,5);ctx.lineTo(0,9);ctx.lineTo(4,5);ctx.stroke();ctx.restore();
  }else{console.log('[分支] 无可编辑选择');}
  console.log('[结束] 选中对象控制柄');
  const selected=layout.elements.find(element=>element.id===options.selectedId);
  console.log('[开始] 线条端点控制柄');
  if(selected&&!selected.locked&&IsLine(selected)){
    console.log('[分支] 显示可拖动端点');ctx.save();ctx.transform(...worldMatrix(layout,selected));
    console.log('[开始] 端点循环');
    selected.shape.points.forEach((point,index)=>{console.log(`[开始] 端点 ${index+1}/2`);ctx.beginPath();ctx.arc((selected.flipX?1-point.x:point.x)*selected.width,(selected.flipY?1-point.y:point.y)*selected.height,7/v.scale,0,Math.PI*2);ctx.fillStyle='#fff';ctx.fill();ctx.strokeStyle='#ff6b2c';ctx.lineWidth=2/v.scale;ctx.stroke();console.log(`[结束] 端点 ${index+1}/2`);});
    console.log('[结束] 端点循环');ctx.restore();
  }else{console.log('[分支] 无端点控制');}
  console.log('[结束] 线条端点控制柄');
  if(options.selectedNode){for(const el of layout.elements){const n=el.route?.nodes.find(n=>n.id===options.selectedNode);if(n){const p=transform(worldMatrix(layout,el),n);ctx.beginPath();ctx.arc(p.x,p.y,14/v.scale,0,Math.PI*2);ctx.strokeStyle='#ff8c36';ctx.lineWidth=5/v.scale;ctx.stroke();}}}ctx.restore();
}
