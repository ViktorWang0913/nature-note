import {test,expect,vi,afterEach} from 'vitest';
vi.mock('../../services/api',()=>({request:vi.fn(),operationId:()=> 'drawing-operation'}));
vi.mock('../../services/projects',()=>({chooseProject:vi.fn(),setCurrentProject:vi.fn()}));
vi.mock('../../services/local-store',()=>({}));
vi.mock('../../engine/render',()=>({loadImages:vi.fn(),renderScene:vi.fn()}));
import definition from '../design/logic';
import {History} from '../../engine/scene';
import {BuildStroke,HitDrawing} from '../../engine/drawing';

function BuildEditor(){
  const layout:any={schema_version:1,notebookVersion:1,designMode:'manual',width:1024,height:1536,background:'#ffffff',elements:[]};
  const editor:any={...definition,data:structuredClone(definition.data),layout,history:new History(layout),images:new Map(),
    viewport:{x:0,y:0,scale:1},canvasWidth:1024,canvasHeight:1536,Draw:vi.fn(),ScheduleCanvas:vi.fn(),RefreshImages:async()=>{},
    setData(patch:any){Object.assign(this.data,patch);}};
  vi.stubGlobal('wx',{enableAlertBeforeUnload:vi.fn(),disableAlertBeforeUnload:vi.fn(),hideKeyboard:vi.fn(),showModal:({success})=>success({confirm:true})});
  editor.savedSignature=editor.Signature();return editor;
}
function Event(points:{x:number;y:number}[]){return {touches:points};}
afterEach(()=>vi.unstubAllGlobals());

test('one stroke is one undo, tap creates dot, positions survive normalized scaling',()=>{
  const editor=BuildEditor();editor.data.drawingMode=true;
  editor.TouchStart(Event([{x:100,y:200}]));editor.TouchMove(Event([{x:200,y:250}]));editor.TouchMove(Event([{x:300,y:240}]));editor.TouchEnd();
  const stroke=editor.layout.elements[0];expect(stroke.stroke.points).toHaveLength(3);
  expect(stroke.x+stroke.stroke.points[0].x*stroke.width).toBe(100);
  editor.Undo();expect(editor.layout.elements).toHaveLength(0);editor.Redo();expect(editor.layout.elements).toHaveLength(1);
  editor.TouchStart(Event([{x:400,y:400}]));editor.TouchEnd();expect(editor.layout.elements[1].stroke.points).toHaveLength(1);
});
test('second finger cancels in-progress stroke and does not draw when fingers lift one at a time',()=>{
  const editor=BuildEditor();editor.data.drawingMode=true;
  editor.TouchStart(Event([{x:100,y:200}]));editor.TouchMove(Event([{x:120,y:220}]));
  editor.TouchStart(Event([{x:120,y:220},{x:180,y:220}]));
  editor.TouchMove(Event([{x:100,y:220},{x:200,y:220}]));
  editor.TouchEnd(Event([{x:100,y:220}]));editor.TouchMove(Event([{x:110,y:230}]));editor.TouchEnd(Event([]));
  expect(editor.layout.elements).toHaveLength(0);expect(editor.panOnly).toBe(false);expect(editor.history.canUndo).toBe(false);
});
test('system pointer cancellation restores an unfinished stroke',()=>{
  const editor=BuildEditor();editor.data.drawingMode=true;editor.TouchStart(Event([{x:100,y:200}]));
  editor.TouchEnd({touches:[],nativeEvent:{type:'pointercancel'}});expect(editor.layout.elements).toHaveLength(0);
});
test('eraser hits actual stroke, preserves locked strokes and allows undo',()=>{
  const editor=BuildEditor();
  const stroke=BuildStroke([{x:100,y:100},{x:200,y:200}],8,'#334455',.5,'stroke',1,'pen');
  expect(HitDrawing(stroke,{x:stroke.width,y:0},1)).toBe(false);
  editor.Commit({...editor.layout,elements:[stroke,{...structuredClone(stroke),id:'locked',locked:true}]});
  editor.data.drawingMode=true;editor.data.brushKind='eraser';editor.TouchStart(Event([{x:150,y:150}]));editor.TouchEnd();
  expect(editor.layout.elements.map(item=>item.id)).toEqual(['locked']);editor.Undo();expect(editor.layout.elements).toHaveLength(2);
});
test('style slider previews collapse to one undo and reject invisible shape',()=>{
  const editor=BuildEditor();editor.AddShape({currentTarget:{dataset:{kind:'circle'}}});
  editor.OpenStyle();editor.StyleInput({currentTarget:{dataset:{field:'opacity'}},detail:{value:20}});
  editor.StyleInput({currentTarget:{dataset:{field:'opacity'}},detail:{value:35}});editor.FinishStyle();
  expect(editor.layout.elements[0].opacity).toBe(.35);editor.Undo();expect(editor.layout.elements[0].opacity).toBe(1);
  editor.Select(editor.layout.elements[0].id);editor.ApplyStyle({currentTarget:{dataset:{field:'fill',value:'none'}}});
  editor.ApplyStyle({currentTarget:{dataset:{field:'stroke',value:'none'}}});expect(editor.layout.elements[0].shape.stroke).toBe('#416b55');
});
test('line endpoint changes direction and length without converting into raster content',()=>{
  const editor=BuildEditor();editor.AddShape({currentTarget:{dataset:{kind:'arrow'}}});const line=editor.layout.elements[0];
  editor.TouchStart(Event([{x:line.x+line.width,y:line.y+line.height/2}]));
  editor.TouchMove(Event([{x:800,y:400}]));editor.TouchEnd();
  const result=editor.layout.elements[0],end=result.shape.points[1];
  expect(result.x+end.x*result.width).toBe(800);expect(result.y+end.y*result.height).toBe(400);
  editor.Undo();expect(editor.layout.elements[0]).toEqual(line);
});
test('unlocked ratio allows nonuniform resize',()=>{
  const editor=BuildEditor();editor.AddShape({currentTarget:{dataset:{kind:'rectangle'}}});
  editor.ApplyStyle({currentTarget:{dataset:{field:'lockRatio'}},detail:{value:false}});
  const shape=structuredClone(editor.layout.elements[0]);
  editor.TouchStart(Event([{x:shape.x+shape.width,y:shape.y+shape.height}]));
  editor.TouchMove(Event([{x:shape.x+shape.width*1.5,y:shape.y+shape.height}]));editor.TouchEnd();
  expect(editor.layout.elements[0].width).toBeCloseTo(shape.width*1.5);expect(editor.layout.elements[0].height).toBeCloseTo(shape.height);
});
test('dragging a tiny dot does not silently enlarge it to the control size',()=>{
  const editor=BuildEditor();const dot=BuildStroke([{x:400,y:400}],1,'#334455',1,'tiny',1,'dot');
  editor.Commit({...editor.layout,elements:[dot]});
  editor.TouchStart(Event([{x:400,y:400}]));editor.TouchMove(Event([{x:430,y:420}]));editor.TouchEnd();
  expect(editor.layout.elements[0].width).toBe(dot.width);expect(editor.layout.elements[0].height).toBe(dot.height);
  expect(editor.layout.elements[0].x).toBe(dot.x+30);
});
test('resize keeps object size, centers positions, saves dimensions and undo restores',async()=>{
  const editor=BuildEditor();editor.AddShape({currentTarget:{dataset:{kind:'star'}}});const before=structuredClone(editor.layout);
  editor.OpenPaper();editor.data.paperForm={width:800,height:800,background:'#eeeeee'};await editor.ApplyPaper();
  expect(editor.layout.width).toBe(800);expect(editor.layout.elements[0].width).toBe(before.elements[0].width);
  expect(editor.layout.elements[0].x).toBe(before.elements[0].x-112);editor.Undo();expect(editor.layout).toEqual(before);
});

// 修复回归：真实比例、外置控制柄和一次拖动对应一次历史记录。
import {ControlGeometry,HitControl} from '../../engine/notebook-controls';
import {transform,worldMatrix,screenToCanvas} from '../../engine/scene';

test('resizing the viewport preserves absolute scale and the world point at the center',async()=>{
  const editor=BuildEditor(),canvas={getContext:()=>({})};
  editor.canvas=canvas;editor.canvasWidth=400;editor.canvasHeight=600;editor.viewport={x:-120,y:-240,scale:.8};
  const anchor=screenToCanvas({x:200,y:300},editor.viewport);
  editor.createSelectorQuery=()=>({select:()=>({fields:()=>({exec:callback=>callback([{node:canvas,width:320,height:480}])})})});
  Object.assign(wx,{nextTick:callback=>callback(),getWindowInfo:()=>({pixelRatio:2})});
  await editor.SetupCanvas();
  expect(editor.viewport.scale).toBe(.8);expect(screenToCanvas({x:160,y:240},editor.viewport)).toEqual(anchor);
  expect(canvas.width).toBe(640);expect(editor.history.canUndo).toBe(false);
});

test('late image completion cannot reset a zoom performed during loading',async()=>{
  const editor=BuildEditor(),canvas={getContext:()=>({})};let finishRead:()=>void;
  editor.canvas=canvas;editor.canvasWidth=400;editor.canvasHeight=600;editor.viewport={x:0,y:0,scale:1};
  editor.RefreshImages=()=>new Promise<void>(resolve=>{finishRead=resolve;});
  editor.createSelectorQuery=()=>({select:()=>({fields:()=>({exec:callback=>callback([{node:canvas,width:320,height:480}])})})});
  Object.assign(wx,{nextTick:callback=>callback(),getWindowInfo:()=>({pixelRatio:1})});
  const pending=editor.SetupCanvas();await Promise.resolve();await Promise.resolve();await Promise.resolve();
  editor.viewport={x:-33,y:-77,scale:2};finishRead();await pending;
  expect(editor.viewport).toEqual({x:-33,y:-77,scale:2});
});

test('resize query that resolves during a gesture defers all canvas mutation',async()=>{
  const editor=BuildEditor(),canvas={getContext:()=>({})};editor.canvas=canvas;
  editor.gesture={count:1};
  editor.createSelectorQuery=()=>({select:()=>({fields:()=>({exec:callback=>callback([{node:canvas,width:320,height:480}])})})});
  Object.assign(wx,{nextTick:callback=>callback()});await editor.SetupCanvas();
  expect(editor.canvasWidth).toBe(1024);expect(editor.ScheduleCanvas).toHaveBeenCalled();
});

test('selected tiny dot body remains moveable and has separated control targets',()=>{
  const editor=BuildEditor(),dot=BuildStroke([{x:400,y:400}],1,'#334455',1,'tiny-selected',1,'dot');
  editor.Commit({...editor.layout,elements:[dot]});editor.Select(dot.id);
  expect(HitControl(editor.layout,dot,{x:400,y:400},editor.viewport)).toBe('');
  editor.TouchStart(Event([{x:400,y:400}]));editor.TouchMove(Event([{x:430,y:420}]));editor.TouchEnd();
  expect(editor.layout.elements[0].width).toBe(dot.width);expect(editor.layout.elements[0].x).toBe(dot.x+30);
});

test('independent move handle translates a tiny rotated shape, undo restores, lock prevents movement',()=>{
  const editor=BuildEditor();editor.AddShape({currentTarget:{dataset:{kind:'rectangle'}}});
  Object.assign(editor.layout.elements[0],{x:300,y:400,width:6,height:8,rotation:37});editor.Commit(structuredClone(editor.layout));
  const shape=structuredClone(editor.layout.elements[0]),controls=ControlGeometry(editor.layout,shape,editor.viewport,{width:1024,height:1536});
  const point=transform(worldMatrix(editor.layout,shape),controls.move);
  editor.TouchStart(Event([point]));expect(editor.gesture.control).toBe('move');
  editor.TouchMove(Event([{x:point.x+40,y:point.y+30}]));editor.TouchEnd();
  expect(editor.layout.elements[0]).toEqual({...shape,x:shape.x+40,y:shape.y+30});
  editor.Undo();expect(editor.layout.elements[0]).toEqual(shape);editor.Redo();
  const moved=editor.layout.elements[0];moved.locked=true;
  expect(HitControl(editor.layout,moved,point,editor.viewport)).toBe('');
});

test('expanded corner free resize measures movement from the original size without a jump',()=>{
  const editor=BuildEditor();editor.AddShape({currentTarget:{dataset:{kind:'rectangle'}}});
  const shape=editor.layout.elements[0];Object.assign(shape,{x:300,y:400,width:20,height:20});shape.shape.lockRatio=false;
  const corner=ControlGeometry(editor.layout,shape,editor.viewport).corners[3],point=transform(worldMatrix(editor.layout,shape),corner);
  editor.TouchStart(Event([point]));editor.TouchMove(Event([{x:point.x+10,y:point.y+5}]));editor.TouchEnd();
  expect(editor.layout.elements[0].width).toBeCloseTo(30);expect(editor.layout.elements[0].height).toBeCloseTo(25);
  expect(editor.layout.elements[0].x).toBeCloseTo(300);expect(editor.layout.elements[0].y).toBeCloseTo(400);
});

test('move handle changes sides at the edge and keeps its 44 pixel target away from corners',()=>{
  const editor=BuildEditor();editor.AddShape({currentTarget:{dataset:{kind:'circle'}}});
  const shape=editor.layout.elements[0];Object.assign(shape,{x:290,y:200,width:10,height:10});
  const controls=ControlGeometry(editor.layout,shape,editor.viewport,{width:320,height:480});
  expect(controls.moveScreen.x).toBeLessThan(290);expect(controls.moveScreen.x).toBeGreaterThanOrEqual(24);
  const nearest=Math.min(...controls.corners.map(corner=>{const point=transform(worldMatrix(editor.layout,shape),corner);return Math.hypot(point.x-controls.moveScreen.x,point.y-controls.moveScreen.y);}));
  expect(nearest).toBeGreaterThan(34);
});
