import { Layout, SceneElement, Asset, RouteNode, TrackPoint } from '../types/models';

import {HitDrawing,IsLine} from './drawing';

export interface Point { x: number; y: number }
export type Matrix = [number, number, number, number, number, number];
export interface Viewport { x: number; y: number; scale: number }
export const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value));
export function uid(prefix = 'el'): string { return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`; }
export function multiply(a: Matrix, b: Matrix): Matrix {
  return [a[0]*b[0]+a[2]*b[1], a[1]*b[0]+a[3]*b[1], a[0]*b[2]+a[2]*b[3], a[1]*b[2]+a[3]*b[3], a[0]*b[4]+a[2]*b[5]+a[4], a[1]*b[4]+a[3]*b[5]+a[5]];
}
export function inverse(a: Matrix): Matrix {
  const d=a[0]*a[3]-a[1]*a[2]; if (Math.abs(d)<1e-12) throw new Error('无效坐标变换');
  return [a[3]/d,-a[1]/d,-a[2]/d,a[0]/d,(a[2]*a[5]-a[3]*a[4])/d,(a[1]*a[4]-a[0]*a[5])/d];
}
export function transform(m: Matrix, p: Point): Point { return {x:m[0]*p.x+m[2]*p.y+m[4],y:m[1]*p.x+m[3]*p.y+m[5]}; }
export function localMatrix(el: SceneElement): Matrix {
  const r=el.rotation*Math.PI/180,c=Math.cos(r),s=Math.sin(r),cx=el.width/2,cy=el.height/2;
  return [c,s,-s,c,el.x+cx-c*cx+s*cy,el.y+cy-s*cx-c*cy];
}
export function worldMatrix(layout: Layout, el: SceneElement, visited=new Set<string>()): Matrix {
  if (visited.has(el.id)) throw new Error('循环分组'); visited.add(el.id);
  const parent=layout.elements.find(e=>e.id===el.parent_id);
  return parent?multiply(worldMatrix(layout,parent,visited),localMatrix(el)):localMatrix(el);
}
export function screenToCanvas(p: Point,v: Viewport): Point {return {x:(p.x-v.x)/v.scale,y:(p.y-v.y)/v.scale};}
export function canvasToScreen(p: Point,v: Viewport): Point {return {x:p.x*v.scale+v.x,y:p.y*v.scale+v.y};}
export function fitViewport(layout: Layout,width: number,height: number,padding=14): Viewport {
  const scale=Math.min((width-padding*2)/layout.width,(height-padding*2)/layout.height);
  return {scale,x:(width-layout.width*scale)/2,y:(height-layout.height*scale)/2};
}
export function hitElement(layout: Layout,p: Point): SceneElement|undefined {
  return [...layout.elements].sort((a,b)=>b.z-a.z).find(el=>{ const q=transform(inverse(worldMatrix(layout,el)),p); q.x=el.flipX?el.width-q.x:q.x;q.y=el.flipY?el.height-q.y:q.y;return el.type==='stroke'||IsLine(el)?HitDrawing(el,q):q.x>=0&&q.y>=0&&q.x<=el.width&&q.y<=el.height; });
}
export function hitNode(layout: Layout,p: Point,tolerance=90): {element: SceneElement;node: RouteNode}|undefined {
  for (const el of [...layout.elements].reverse()) if(el.route) for(const n of el.route.nodes){const q=transform(worldMatrix(layout,el),n); if(Math.hypot(q.x-p.x,q.y-p.y)<=tolerance)return {element:el,node:n};}
  return undefined;
}
export function moveElement(layout: Layout,id: string,delta: Point): Layout {
  const next=clone(layout),el=next.elements.find(e=>e.id===id);if(!el)return next;
  const parent=next.elements.find(e=>e.id===el.parent_id);
  if(parent){const inv=inverse(worldMatrix(next,parent)),a=transform(inv,{x:0,y:0}),b=transform(inv,delta);el.x+=b.x-a.x;el.y+=b.y-a.y;}else{el.x+=delta.x;el.y+=delta.y;}return next;
}
export function resizeElement(layout: Layout,id: string,factor: number): Layout {
  const next=clone(layout),el=next.elements.find(e=>e.id===id); if(!el)return next;
  factor=Math.max(.1,Math.min(10,factor));el.width*=factor;el.height*=factor;
  if(el.route){el.route.points.forEach(p=>{p.x*=factor;p.y*=factor;});el.route.nodes.forEach(n=>{n.x*=factor;n.y*=factor;});
    const segs=(el.route as any).segments as Point[][]|undefined;segs?.forEach(s=>s.forEach(p=>{p.x*=factor;p.y*=factor;}));
    for(const child of next.elements.filter(c=>c.parent_id===id)){child.x*=factor;child.y*=factor;child.width*=factor;child.height*=factor;child.fontSize=child.fontSize?child.fontSize*factor:undefined;}}
  return next;
}
export function attachAsset(layout: Layout,asset: Asset,p: Point,nodeHit?: {element:SceneElement;node:RouteNode}): Layout {
  const next=clone(layout);const size=Math.min(layout.width,layout.height)*.14;
  const el:SceneElement={id:uid(),type:'image',x:p.x-size/2,y:p.y-size/2,width:size,height:size,rotation:0,z:Math.max(0,...next.elements.map(e=>e.z))+1,asset_id:asset.id,url:asset.url};
  if(nodeHit){const route=next.elements.find(e=>e.id===nodeHit.element.id)!;const node=route.route!.nodes.find(n=>n.id===nodeHit.node.id)!;const q=transform(inverse(worldMatrix(next,route)),p);el.parent_id=route.id;el.node_id=node.id;el.x=q.x-size/2;el.y=q.y-size/2;node.asset_ids=Array.from(new Set([...(node.asset_ids||[]),asset.id]));node.cover_asset_id=node.cover_asset_id||asset.id;}
  next.elements.push(el);return next;
}
export function deleteElement(layout: Layout,id: string): Layout {const next=clone(layout);const removed=next.elements.find(e=>e.id===id);next.elements=next.elements.filter(e=>e.id!==id&&e.parent_id!==id);if(removed?.node_id&&removed.asset_id){const n=next.elements.find(e=>e.id===removed.parent_id)?.route?.nodes.find(n=>n.id===removed.node_id);if(n&&!next.elements.some(e=>e.node_id===n.id&&e.asset_id===removed.asset_id)){n.asset_ids=n.asset_ids?.filter(a=>a!==removed.asset_id);if(n.cover_asset_id===removed.asset_id)n.cover_asset_id=n.asset_ids?.[0];}}return next;}
export function moveNode(layout: Layout,routeId: string,nodeId: string,world: Point): Layout {
  const next=clone(layout),el=next.elements.find(e=>e.id===routeId);if(!el?.route)return next;const n=el.route.nodes.find(n=>n.id===nodeId);if(!n)return next;const q=transform(inverse(worldMatrix(next,el)),world),dx=q.x-n.x,dy=q.y-n.y;
  const closest=el.route.points.reduce((best,p,i)=>Math.hypot(p.x-n.x,p.y-n.y)<best.dist?{dist:Math.hypot(p.x-n.x,p.y-n.y),i}:best,{dist:Infinity,i:-1});
  if(closest.i>=0){const old=el.route.points[closest.i];const segs=(el.route as any).segments as Point[][]|undefined;segs?.forEach(s=>s.forEach(p=>{if(Math.abs(p.x-old.x)<.01&&Math.abs(p.y-old.y)<.01){p.x=q.x;p.y=q.y;}}));el.route.points[closest.i]={...q};}
  n.x=q.x;n.y=q.y;next.elements.filter(e=>e.parent_id===routeId&&e.node_id===nodeId).forEach(e=>{e.x+=dx;e.y+=dy;});return next;
}
export function validateLayout(value: any): value is Layout {
  if(!value||value.schema_version!==1||!Number.isFinite(value.width)||!Number.isFinite(value.height)||value.width<100||value.height<100||value.width>8192||value.height>8192||!Array.isArray(value.elements)||value.elements.length>500)return false;
  const ids=new Set<string>();for(const e of value.elements){if(!e||ids.has(e.id)||!['image','text','route','stroke','shape'].includes(e.type)||!['x','y','width','height','rotation','z'].every(k=>Number.isFinite(e[k]))||e.width<=0||e.height<=0)return false;ids.add(e.id);}
  for(const e of value.elements){if(e.parent_id&&!ids.has(e.parent_id))return false;try{worldMatrix(value,e);}catch(_){return false;}if(e.route&&(!Array.isArray(e.route.points)||!Array.isArray(e.route.nodes)||![...e.route.points,...e.route.nodes].every((p:any)=>Number.isFinite(p.x)&&Number.isFinite(p.y))))return false;}return true;
}
export function trackToRoute(track: {id:string;points:TrackPoint[];nodes:any[]},width: number,height: number): SceneElement {
  const all=[...track.points,...track.nodes].filter(p=>Number.isFinite(p.latitude)&&Number.isFinite(p.longitude));
  if(!all.length)throw new Error('轨迹没有有效位置');const avg=all.reduce((s,p)=>s+p.latitude,0)/all.length,c=Math.cos(avg*Math.PI/180),xs=all.map(p=>p.longitude*c),ys=all.map(p=>-p.latitude),minX=Math.min(...xs),minY=Math.min(...ys),rangeX=Math.max(...xs)-minX,rangeY=Math.max(...ys)-minY;
  const w=width*.8,h=height*.6,scale=Math.min(w/Math.max(rangeX,.00001),h/Math.max(rangeY,.00001)),padX=(w-rangeX*scale)/2,padY=(h-rangeY*scale)/2;
  const project=(p:any)=>({x:(p.longitude*c-minX)*scale+padX,y:(-p.latitude-minY)*scale+padY});
  const segments:Point[][]=[];let segment=-1;for(const p of track.points){if(p.segment!==segment){segments.push([]);segment=p.segment;}segments[segments.length-1].push(project(p));}
  const route:any={style:'smooth',points:track.points.map(project),segments,nodes:track.nodes.map((n,i)=>({...project(n),id:n.id,label:String(i+1).padStart(2,'0'),text:n.text,asset_ids:n.asset_ids||[],cover_asset_id:n.cover_asset_id})),track_id:track.id,color:'#bbb9b3',lineWidth:45};
  return {id:uid('route'),type:'route',x:width*.1,y:height*.22,width:w,height:h,rotation:0,z:1,route};
}
export class History {
  private past:Layout[]=[];private future:Layout[]=[];current:Layout;
  constructor(layout:Layout){this.current=clone(layout);}
  commit(layout:Layout):void {if(JSON.stringify(layout)===JSON.stringify(this.current))return;this.past.push(clone(this.current));if(this.past.length>40)this.past.shift();this.current=clone(layout);this.future=[];}
  undo():Layout {if(this.past.length){this.future.push(clone(this.current));this.current=this.past.pop()!;}return clone(this.current);}
  redo():Layout {if(this.future.length){this.past.push(clone(this.current));this.current=this.future.pop()!;}return clone(this.current);}
  get canUndo(){return this.past.length>0;}get canRedo(){return this.future.length>0;}
}
