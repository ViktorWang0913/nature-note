import {beforeEach,expect,test,vi} from 'vitest';
vi.mock('../../services/api',()=>({request:vi.fn()}));
vi.mock('../../services/projects',()=>({currentProjectId:vi.fn(),setCurrentProject:vi.fn(),deleteProject:vi.fn()}));
vi.mock('../../components/flows',()=>({go:vi.fn(),confirm:vi.fn(),fail:vi.fn()}));
import definition from './logic';
import {request} from '../../services/api';
import {deleteProject,setCurrentProject} from '../../services/projects';
import {confirm,go} from '../../components/flows';
function Page(){return {...definition,data:structuredClone(definition.data),setData(patch:any){Object.assign(this.data,patch);}} as any;}
beforeEach(()=>vi.resetAllMocks());
test('skips pages of manual designs and retains pagination for observation projects',async()=>{
  vi.mocked(request).mockResolvedValueOnce({items:[{id:'manual',layout:{designMode:'manual'}}],next_cursor:'next'}).mockResolvedValueOnce({items:[{id:'observation',layout:{}}],next_cursor:'more'}).mockResolvedValueOnce({items:[{id:'second',layout:{}}],next_cursor:null});
  const page=Page();await page.load();expect(page.data.items.map(item=>item.id)).toEqual(['observation']);expect(page.data.next).toBe('more');await page.More();expect(page.data.items.map(item=>item.id)).toEqual(['observation','second']);
});
test('empty projects and failed reads have distinct states and can retry',async()=>{
  const page=Page();vi.mocked(request).mockRejectedValueOnce(new Error('网络不可用')).mockResolvedValueOnce({items:[],next_cursor:null});
  await page.load();expect(page.data.error).toBe('网络不可用');expect(page.data.loading).toBe(false);await page.load();expect(page.data.items).toEqual([]);expect(page.data.error).toBe('');
});
test('continue uses the selected project and cancelling deletion preserves it',async()=>{
  const page=Page(),event={currentTarget:{dataset:{id:'observation'}}};page.Continue(event);expect(setCurrentProject).toHaveBeenCalledWith('observation');expect(go).toHaveBeenCalledWith('/pages/gps/index?projectId=observation');
  vi.mocked(confirm).mockResolvedValue(false);await page.remove(event);expect(deleteProject).not.toHaveBeenCalled();expect(page.data.removingId).toBe('');
});

test('my notes pagination retains both manual and observation notebooks',async()=>{
  const {default:projects}=await import('../projects/logic');
  const page:any={...projects,data:structuredClone(projects.data),setData(patch:any){Object.assign(this.data,patch);}};
  vi.mocked(request).mockResolvedValueOnce({items:[{id:'manual',layout:{designMode:'manual'}}],next_cursor:'older'}).mockResolvedValueOnce({items:[{id:'observation',layout:{}}],next_cursor:null});
  await page.load();await page.More();expect(page.data.items.map(item=>item.id)).toEqual(['manual','observation']);expect(page.data.next).toBe('');
});
