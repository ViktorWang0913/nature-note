import {expect,test,vi} from 'vitest';
vi.mock('../web/media',()=>({CachedImage:vi.fn()}));
import {manualTemplate} from './templates';
import {Layout} from '../types/models';
import {History,worldMatrix,transform} from './scene';
function Template(style:'smooth'|'orthogonal'='smooth'):Layout{return {schema_version:1,width:3600,height:2400,background:'#fff8dc',elements:[{id:'route',type:'route',x:260,y:530,width:2880,height:1450,rotation:31,z:1,route:{style,points:[{x:150,y:800},{x:700,y:400},{x:1400,y:720}],nodes:[{id:'demo-node',x:1400,y:720,label:'01'}],color:'#bbb7af',lineWidth:35}},{id:'bird',type:'image',x:880,y:30,width:670,height:620,rotation:12,z:2,parent_id:'route',node_id:'demo-node',asset_id:'public-bulbul',url:'/bird.png'},{id:'title',type:'text',x:160,y:90,width:2400,height:170,rotation:0,z:3,text:'校园观鸟笔记',fontSize:104,color:'#453c2d'}]};}
test.each(['smooth','orthogonal'] as const)('converts %s templates into editable layers without observation references',style=>{
  const original=Template(style),before=JSON.stringify(original),result=manualTemplate(original);
  expect(JSON.stringify(original)).toBe(before);
  expect(result).toMatchObject({designMode:'manual',notebookVersion:1,width:3600,height:2400});
  expect(result.elements.every(element=>element.type!=='route'&&!element.parent_id&&!element.node_id)).toBe(true);
  expect(new Set(result.elements.map(element=>element.id)).size).toBe(result.elements.length);
  const image=result.elements.find(element=>element.type==='image')!;
  for(const point of [{x:0,y:0},{x:670,y:620}]){
    const expected=transform(worldMatrix(original,original.elements[1]),point),actual=transform(worldMatrix(result,image),point);
    expect(actual.x).toBeCloseTo(expected.x);expect(actual.y).toBeCloseTo(expected.y);
  }
  expect(result.elements.find(element=>element.type==='text'&&element.text==='01')).toBeDefined();
  const history=new History(original);history.commit(result);expect(history.undo()).toEqual(original);expect(history.redo()).toEqual(result);
});
test('rejects invalid or oversized templates before replacing the board',()=>{
  const invalid=Template();invalid.width=5000;expect(()=>manualTemplate(invalid)).toThrow('尺寸');
  const excessive=Template();excessive.elements=Array.from({length:201},(_,i)=>({...excessive.elements[2],id:String(i)}));expect(()=>manualTemplate(excessive)).toThrow('图层');
  const broken=Template();broken.elements[1].parent_id='missing';expect(()=>manualTemplate(broken)).toThrow();
});
