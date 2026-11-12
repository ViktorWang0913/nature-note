import {beforeEach,expect,test,vi} from 'vitest';
vi.mock('../../services/api',()=>({request:vi.fn()}));
import definition from './logic';
import {request} from '../../services/api';
function Page(){return {...definition,data:structuredClone(definition.data),setData(patch:any){Object.assign(this.data,patch);}} as any;}
beforeEach(()=>vi.resetAllMocks());
test('atlas uses the full result total and retains the submitted query when loading more',async()=>{
  vi.mocked(request).mockResolvedValueOnce({items:[{id:'first'}],total:31,next_cursor:'next'}).mockResolvedValueOnce({items:[{id:'second'}],total:31,next_cursor:null});
  const page=Page();await page.load();expect(page.data.total).toBe(31);expect(page.data.items).toHaveLength(1);expect(request).toHaveBeenCalledTimes(1);
  page.data.q='尚未搜索的名字';await page.more();expect(page.data.items).toHaveLength(2);expect(page.data.total).toBe(31);expect(request).toHaveBeenLastCalledWith('/atlas?sort=category&cursor=next');
});
test('a slower previous search cannot replace a newer result',async()=>{
  let finish:(value:any)=>void=()=>{};
  vi.mocked(request).mockImplementationOnce(()=>new Promise(resolve=>finish=resolve)).mockResolvedValueOnce({items:[],total:0,next_cursor:null});
  const page=Page(),first=page.load();page.data.q='  银杏  ';const latest=page.load();await latest;
  finish({items:[{id:'old'}],total:40,next_cursor:'old'});await first;
  expect(page.data.resultQuery).toBe('银杏');expect(page.data.total).toBe(0);expect(page.data.items).toEqual([]);expect(page.data.loading).toBe(false);
});
test('a backend without total shows an explicit loaded count instead of a false total',async()=>{
  vi.mocked(request).mockResolvedValueOnce({items:[{id:'first'}],next_cursor:'next'});
  const page=Page();await page.load();expect(page.data.total).toBeNull();expect(page.data.items).toHaveLength(1);
});
