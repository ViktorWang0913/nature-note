import {expect,test,vi} from 'vitest';
vi.mock('../web/media',()=>({CachedImage:vi.fn().mockResolvedValue('blob:new-image')}));
import {CachedImage} from '../web/media';
import {loadImages} from './render';

test('inserting, saving and exporting reuse original decoded pixels',async()=>{
  const background={width:1024,height:1536},leaf={width:1254,height:1254,onload:()=>{},onerror:()=>{},set src(value:string){queueMicrotask(()=>this.onload());}};
  const canvas={createImage:vi.fn(()=>leaf)},previous=new Map([['/background.png',background]]);
  const layout:any={elements:[{id:'background',type:'image',url:'/background.png'},{id:'leaf',type:'image',url:'/leaf.png'}]};
  const loaded=await loadImages(canvas,layout,previous);
  expect(CachedImage).toHaveBeenCalledTimes(1);
  expect(loaded.get('/background.png')).toBe(background);
  expect(loaded.get('/leaf.png')).toBe(leaf);
  await loadImages(canvas,layout,loaded);
  await loadImages({createImage:vi.fn()},layout,loaded);
  expect(CachedImage).toHaveBeenCalledTimes(1);
  expect(canvas.createImage).toHaveBeenCalledTimes(1);
  expect(leaf.width).toBe(1254);
});
