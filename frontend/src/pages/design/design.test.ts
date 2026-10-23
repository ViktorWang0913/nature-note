import {expect,test,vi} from 'vitest';
vi.mock('../../services/api',()=>({request:vi.fn(),operationId:()=> 'test-operation'}));
vi.mock('../../services/projects',()=>({chooseProject:vi.fn(),setCurrentProject:vi.fn()}));
vi.mock('../../services/local-store',()=>({}));
vi.mock('../../engine/render',()=>({loadImages:vi.fn(),renderScene:vi.fn()}));
import definition from './logic';
import {History} from '../../engine/scene';

// 自编函数
function BuildEditor(){
  const layout={schema_version:1 as const,notebookVersion:1 as const,designMode:'manual' as const,
    width:1024,height:1536,background:'#ffffff',elements:[]};
  const editor:any={...definition,data:structuredClone(definition.data),layout,history:new History(layout),
    context:{measureText:(value:string)=>({width:value.length*24})},canvasWidth:1024,canvasHeight:1536,
    viewport:{x:0,y:0,scale:1},Draw:vi.fn(),ScheduleCanvas:vi.fn(),RefreshImages:async()=>{},
    setData(patch:any){Object.assign(this.data,patch);}};
  vi.stubGlobal('wx',{enableAlertBeforeUnload:vi.fn(),disableAlertBeforeUnload:vi.fn(),hideKeyboard:vi.fn()});
  editor.savedSignature=editor.Signature();return editor;
}

test('first text on empty board has valid order and can undo to empty',()=>{
  const editor=BuildEditor();editor.data.textForm.text='观察笔记';editor.ApplyText();
  expect(editor.layout.elements[0].z).toBe(1);
  expect(editor.layout.elements[0].height).toBeGreaterThan(0);
  editor.Undo();expect(editor.layout.elements).toEqual([]);
  vi.unstubAllGlobals();
});

test('copy, flip and lock are undoable and locked objects reject edits',()=>{
  const editor=BuildEditor();editor.data.textForm.text='叶片';editor.ApplyText();
  const Run=(action:string)=>editor.ElementAction({currentTarget:{dataset:{action}}});
  Run('duplicate');expect(editor.layout.elements).toHaveLength(2);
  Run('flipX');expect(editor.layout.elements[1].flipX).toBe(true);
  Run('lock');const locked=structuredClone(editor.layout);
  Run('centerX');editor.Remove();expect(editor.layout).toEqual(locked);
  editor.TouchStart({touches:[{x:560,y:780}]});editor.TouchMove({touches:[{x:570,y:790}]});editor.TouchEnd();
  expect(editor.layout.elements).toEqual(locked.elements);
  editor.Undo();expect(editor.layout.elements[1].locked).not.toBe(true);
  vi.unstubAllGlobals();
});

test('title and paper color participate in unsaved state',()=>{
  const editor=BuildEditor();editor.TitleInput({detail:{value:'新标题'}});expect(editor.data.dirty).toBe(true);
  editor.TitleInput({detail:{value:definition.data.title}});expect(editor.data.dirty).toBe(false);
  editor.PaperColor({detail:{value:'#334455'}});expect(editor.data.dirty).toBe(true);
  editor.Undo();expect(editor.data.backgroundColor).toBe('#ffffff');expect(editor.data.dirty).toBe(false);
  vi.unstubAllGlobals();
});
