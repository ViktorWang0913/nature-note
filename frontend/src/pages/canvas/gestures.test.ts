import {expect,test,vi} from 'vitest';
vi.mock('../../services/api',()=>({request:vi.fn()}));
vi.mock('../../services/projects',()=>({chooseProject:vi.fn(),setCurrentProject:vi.fn()}));
vi.mock('../../services/local-store',()=>({}));
vi.mock('../../engine/render',()=>({loadImages:vi.fn(),renderScene:vi.fn()}));
import definition from './logic';
import {History} from '../../engine/scene';

test('multiple redraw requests share one animation frame and keep latest state',()=>{
  let DrawFrame:()=>void=()=>{};
  vi.stubGlobal('requestAnimationFrame',vi.fn(callback=>{DrawFrame=callback;return 1;}));
  const editor:any={...definition,DrawNow:vi.fn()};
  editor.Draw();editor.Draw();editor.Draw();
  expect(requestAnimationFrame).toHaveBeenCalledTimes(1);
  DrawFrame();expect(editor.DrawNow).toHaveBeenCalledTimes(1);
  expect(editor.drawFrame).toBe(0);vi.unstubAllGlobals();
});

function BuildEditor(){
  const layout:any={schema_version:1,width:1024,height:1536,background:'#fff',elements:[
    {id:'background',type:'image',x:0,y:0,width:1024,height:1536,rotation:0,z:0},
    {id:'bird',type:'image',x:100,y:100,width:200,height:160,rotation:0,z:1}
  ]};
  return {...definition,layout,viewport:{x:0,y:0,scale:1},history:new History(layout),
    data:{...structuredClone(definition.data),selectedId:'bird'},
    setData(patch:any){Object.assign(this.data,patch);},Draw:vi.fn(),UpdateDirty:vi.fn()};
}

test('corner scales around center and rotation handle turns without moving center',()=>{
  const editor=BuildEditor();
  editor.TouchStart({touches:[{x:300,y:260}]});
  editor.TouchMove({touches:[{x:400,y:340}]});editor.TouchEnd();
  expect(editor.layout.elements[1].width).toBeCloseTo(400);
  expect(editor.layout.elements[1].x+editor.layout.elements[1].width/2).toBeCloseTo(200);
  editor.TouchStart({touches:[{x:200,y:-4}]});
  editor.TouchMove({touches:[{x:384,y:180}]});editor.TouchEnd();
  expect(editor.layout.elements[1].rotation).toBeCloseTo(90);
  expect(editor.history.undo().elements[1].rotation).toBe(0);
  expect(editor.history.undo().elements[1].width).toBe(200);
  expect(editor.layout.elements[0]).toEqual({id:'background',type:'image',x:0,y:0,width:1024,height:1536,rotation:0,z:0});
});

test('one to two to one pointers keep drag, pinch and subsequent movement undoable',()=>{
  const editor=BuildEditor();
  editor.TouchStart({touches:[{x:200,y:180}]});
  editor.TouchMove({touches:[{x:220,y:200}]});
  editor.TouchStart({touches:[{x:220,y:200},{x:260,y:200}]});
  editor.TouchMove({touches:[{x:220,y:180},{x:260,y:220}]});
  expect(editor.layout.elements[1].rotation).toBeCloseTo(45);
  editor.TouchEnd({touches:[{x:220,y:180}]});
  const position=editor.layout.elements[1].x;
  editor.TouchMove({touches:[{x:230,y:190}]});editor.TouchEnd();
  expect(editor.layout.elements[1].x).toBeCloseTo(position+10);
  expect(editor.history.undo().elements[1].rotation).toBeCloseTo(45);
  expect(editor.history.undo().elements[1].x).toBe(120);
  expect(editor.history.undo().elements[1].x).toBe(100);
});

test('empty pointer lists and blocked input do not mutate layout',()=>{
  const editor=BuildEditor(),original=JSON.stringify(editor.layout);
  editor.TouchStart({touches:[]});editor.TouchMove({touches:[]});
  editor.data.busy=true;editor.TouchStart({touches:[{x:200,y:180}]});
  expect(JSON.stringify(editor.layout)).toBe(original);
});

test('image adjustments preview in scene, cancel restores source and apply is undoable',()=>{
  const editor=BuildEditor();
  editor.ScheduleCanvas=vi.fn();
  vi.stubGlobal('wx',{hideKeyboard:vi.fn()});
  editor.EditMaterial();
  editor.AdjustMaterial({currentTarget:{dataset:{field:'cropW'}},detail:{value:60}});
  editor.FilterMaterial({currentTarget:{dataset:{value:'grayscale'}}});
  expect(editor.layout.elements[1].imageEdit.cropW).toBe(60);
  editor.Leave();expect(editor.layout.elements[1].imageEdit).toBeUndefined();
  editor.EditMaterial();editor.AdjustMaterial({currentTarget:{dataset:{field:'brightness'}},detail:{value:130}});
  editor.ApplyMaterial();expect(editor.layout.elements[1].imageEdit.brightness).toBe(130);
  expect(editor.history.undo().elements[1].imageEdit).toBeUndefined();
  vi.unstubAllGlobals();
});
