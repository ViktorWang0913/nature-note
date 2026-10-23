import { test, vi } from 'vitest';
vi.mock('../web/media',()=>({CachedImage:vi.fn()}));
vi.mock('../services/api',()=>({apiBase:''}));
import { Layout, Asset, TrackPoint } from '../types/models';
import { History, attachAsset, canvasToScreen, clone, inverse, moveElement, resizeElement, screenToCanvas, trackToRoute, transform, validateLayout, worldMatrix } from './scene';
import { renderScene } from './render';
function assert(condition:unknown,message:string):asserts condition {if(!condition)throw new Error(message);}
function near(a:number,b:number){return Math.abs(a-b)<1e-7;}
test('scene geometry, history and disconnected GPS paths remain stable',()=>{
const layout:Layout={schema_version:1,width:3600,height:2400,background:'#fff8dc',elements:[{id:'route',type:'route',x:200,y:400,width:2000,height:1000,rotation:31,z:1,route:{style:'smooth',points:[{x:0,y:0},{x:1500,y:500}],nodes:[{id:'node',label:'01',x:700,y:400}]}}]};
const parent=layout.elements[0],world=transform(worldMatrix(layout,parent),{x:700,y:400}),asset:Asset={id:'bird',name:'白头鹎',url:'/bird.png',category:'birds',source:'generated'};
const attached=attachAsset(layout,asset,world,{element:parent,node:parent.route!.nodes[0]});
assert(attached.elements[1].parent_id==='route'&&attached.elements[1].node_id==='node','drop target must become a node association');
assert(layout.elements.length===1,'adding a material must not mutate prior history');
const free=attachAsset(layout,asset,world);assert(!free.elements[1].parent_id,'blank-canvas drop must remain independent');
const before=transform(worldMatrix(attached,attached.elements[1]),{x:0,y:0}),moved=moveElement(attached,'route',{x:80,y:-50}),after=transform(worldMatrix(moved,moved.elements[1]),{x:0,y:0});
assert(near(after.x-before.x,80)&&near(after.y-before.y,-50),'group move must preserve child relative geometry');
const scaled=resizeElement(attached,'route',1.5);assert(scaled.elements[1].width===attached.elements[1].width*1.5,'group scale must include child size');
const local=transform(inverse(worldMatrix(attached,attached.elements[1])),before);assert(near(local.x,0)&&near(local.y,0),'inverse transform must reverse rotated parent composition');
const view={x:-80,y:42,scale:.245},p={x:1750,y:1600},roundtrip=screenToCanvas(canvasToScreen(p,view),view);assert(near(p.x,roundtrip.x)&&near(p.y,roundtrip.y),'screen and scene conversion must round-trip');
const history=new History(layout);history.commit(attached);history.undo();assert(history.current.elements.length===1,'undo must restore association and element together');history.redo();assert(history.current.elements[1].node_id==='node','redo must restore node association');
const points:TrackPoint[]=[{sequence:0,latitude:31,longitude:121,accuracy:5,timestamp:'2026-10-02T00:00:00Z',segment:0},{sequence:1,latitude:31.001,longitude:121.001,accuracy:5,timestamp:'2026-10-02T00:00:10Z',segment:0},{sequence:2,latitude:31.02,longitude:121.02,accuracy:5,timestamp:'2026-10-02T00:20:00Z',segment:1},{sequence:3,latitude:31.021,longitude:121.021,accuracy:5,timestamp:'2026-10-02T00:20:10Z',segment:1}];
const original=JSON.stringify(points),route=trackToRoute({id:'raw',points,nodes:[]},3600,2400);assert(route.route!.segments!.length===2,'recording interruption must remain separate paths');assert(JSON.stringify(points)===original,'scene creation must not alter raw GPS');
function recordingContext(){const calls:any[]=[];const ctx:any=new Proxy({measureText:(s:string)=>({width:s.length*15})},{get(target:any,key:any){if(key in target)return target[key];return (...args:any[])=>calls.push([key,...args]);},set(target:any,key:any,value:any){target[key]=value;calls.push(['set',key,value]);return true;}});return {ctx,calls};}
const gpsLayout={...clone(layout),elements:[route]},preview=recordingContext(),exported=recordingContext();renderScene(preview.ctx,gpsLayout,new Map(),{viewport:{x:0,y:0,scale:1}});renderScene(exported.ctx,gpsLayout,new Map());assert(JSON.stringify(preview.calls)===JSON.stringify(exported.calls),'preview and export must share geometry rendering');assert(exported.calls.filter(c=>c[0]==='moveTo').length===2,'export must not bridge a GPS gap');assert(validateLayout(attached),'valid nested layout should load');const cyclic=clone(attached);cyclic.elements[0].parent_id=cyclic.elements[1].id;assert(!validateLayout(cyclic),'cyclic parent references must be rejected');
console.log('Scene invariants passed: affine coordinates, parent transforms, node association, history, GPS gaps, shared preview/export, malformed layout.');

});
