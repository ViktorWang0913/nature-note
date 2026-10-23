import { beforeEach, expect, test, vi } from 'vitest';

vi.mock('../../services/workspace',()=>({workspace:{}}));
vi.mock('../../services/local-store',()=>({Get:vi.fn(),Set:vi.fn(),Remove:vi.fn()}));
vi.mock('../../services/sync',()=>({pendingPhotos:vi.fn(),flushQueue:vi.fn()}));
vi.mock('../../services/projects',()=>({currentProjectId:vi.fn(),getCurrentProject:vi.fn(),chooseProject:vi.fn(),importAsset:vi.fn()}));
vi.mock('../../services/api',()=>({request:vi.fn()}));
vi.mock('../../components/flows',()=>({fail:vi.fn(),go:vi.fn(),pickPhoto:vi.fn(),selectTab:vi.fn(),decorateAsset:vi.fn(),query:vi.fn(),waitTask:vi.fn(),preview:vi.fn(),operation:vi.fn()}));

import definition from './logic';
import { request } from '../../services/api';
import { waitTask } from '../../components/flows';
import { currentProjectId, getCurrentProject } from '../../services/projects';
import { decorateAsset } from '../../components/flows';

beforeEach(() => vi.resetAllMocks());

test('slow project title never blocks the material list',async()=>{
  let ResolveTitle:(value:any)=>void;
  vi.mocked(currentProjectId).mockReturnValue('slow-project');
  vi.mocked(getCurrentProject).mockReturnValue(new Promise(resolve=>{ResolveTitle=resolve;}));
  vi.mocked(request).mockResolvedValue({items:[{id:'material'}]});
  vi.mocked(decorateAsset).mockImplementation(value=>value);
  const context:any={...definition,data:{...definition.data,tab:'assets'},setData(patch:any){Object.assign(this.data,patch);}};
  await context.Load();
  expect(context.data.items).toEqual([{id:'material'}]);
  expect(context.data.loading).toBe(false);
  ResolveTitle!({title:'随后到达的笔记名'});
  await Promise.resolve();
  expect(context.data.projectTitle).toBe('随后到达的笔记名');
});

test('late previous filter response cannot replace the new material list',async()=>{
  let ResolveOld:(value:any)=>void;
  vi.mocked(request).mockReturnValueOnce(new Promise(resolve=>{ResolveOld=resolve;})).mockResolvedValueOnce({items:[{id:'new'}]});
  vi.mocked(decorateAsset).mockImplementation(value=>value);
  const context:any={...definition,data:{...definition.data,tab:'assets'},setData(patch:any){Object.assign(this.data,patch);}};
  const previous=context.Load();
  context.data.source='photo';await context.Load();
  ResolveOld!({items:[{id:'old'}]});await previous;
  expect(context.data.items).toEqual([{id:'new'}]);
});

test('任务成功后额度读取失败仍立即显示图片', async () => {
  const completed = { id: 'completed-task', status: 'succeeded', result: { image_url: '/completed.png' } };
  vi.mocked(waitTask).mockResolvedValue(completed as any);
  vi.mocked(request).mockResolvedValueOnce({ messages: [{ task: completed }] }).mockRejectedValueOnce(new Error('额度网络中断'));
  const context: any = { data: { sessionId: 'session', messages: [], busy: true }, _generationEpoch: 1,
    setData(patch: any) { Object.assign(this.data, patch); }, RefreshResults: definition.RefreshResults };
  await definition.CompleteGeneration.call(context, completed.id, 'session', 1);
  expect(context.data.result).toEqual(completed.result);
  expect(context.data.busy).toBe(false);
});

test('已选会话重新进入时重新读取后台结果', async () => {
  const completed = { id: 'completed-task', status: 'succeeded', result: { image_url: '/completed.png' }, input: {} };
  vi.mocked(request).mockResolvedValueOnce({ items: [] }).mockResolvedValueOnce({ id: 'session', title: '创作', messages: [{ task: completed }] });
  const context: any = { data: { sessionId: 'session', messages: [], busy: false }, _generationEpoch: 1,
    setData(patch: any) { Object.assign(this.data, patch); }, RestoreCreationDraft: vi.fn(), RefreshResults: definition.RefreshResults,
    RestoreSession: definition.RestoreSession };
  await definition.LoadSession.call(context);
  expect(request).toHaveBeenCalledWith('/sessions/session');
  expect(context.data.result).toEqual(completed.result);
});

test('恢复尚未完成的会话时自动查询原任务', () => {
  const pending = { id: 'pending-task', status: 'running', input: {} };
  const context: any = { data: { busy: false }, _generationEpoch: 0,
    setData(patch: any) { Object.assign(this.data, patch); }, RefreshResults: vi.fn(),
    CompleteGeneration: vi.fn().mockResolvedValue(undefined), GenerationFailed: vi.fn() };
  definition.RestoreSession.call(context, { id: 'session', messages: [{ task: pending }] });
  expect(context.CompleteGeneration).toHaveBeenCalledWith('pending-task', 'session', 1);
  expect(context.data.busy).toBe(true);
  expect(request).not.toHaveBeenCalled();
});

test('历史仍为处理中不能遮住已取得的成功图片', () => {
  const context: any = { data: { task: { id: 'task' }, messages: [{ task: { id: 'task', status: 'running' } }], scrollTop: 0 },
    setData(patch: any) { Object.assign(this.data, patch); } };
  definition.RefreshResults.call(context);
  expect(context.data.resultHasMessage).toBe(false);
});

test('成功图片先显示，补充请求返回时不覆盖新会话', async () => {
  let resolveSession: (value: any) => void;
  const sessionRead = new Promise(resolve => { resolveSession = resolve; });
  const completed = { id: 'completed-task', status: 'succeeded', result: { image_url: '/completed.png' } };
  vi.mocked(waitTask).mockResolvedValue(completed as any);
  vi.mocked(request).mockReturnValueOnce(sessionRead).mockResolvedValueOnce({ items: [] });
  const context: any = { data: { sessionId: 'session', messages: [], busy: true }, _generationEpoch: 1,
    setData(patch: any) { Object.assign(this.data, patch); }, RefreshResults: definition.RefreshResults };
  const completion = definition.CompleteGeneration.call(context, completed.id, 'session', 1);
  await vi.waitFor(() => expect(context.data.result).toEqual(completed.result));
  context._generationEpoch++;
  context.data.messages = [{ text: '新会话' }];
  resolveSession!({ messages: [{ text: '旧会话' }] });
  await completion;
  expect(context.data.messages).toEqual([{ text: '新会话' }]);
});

test('查询中断后点击重试只恢复原任务，不创建新任务或再次收费',async()=>{
  const completed={id:'original-task',status:'succeeded',result:{image_url:'/private-image'}};
  vi.mocked(waitTask).mockResolvedValue(completed as any);
  vi.mocked(request).mockResolvedValueOnce({messages:[]}).mockResolvedValueOnce({items:[]});
  const context:any={
    data:{busy:false,task:{id:'original-task',status:'running',input:{session_id:'original-session'}},sessionId:'original-session'},
    _generationEpoch:0,
    setData(patch:any){Object.assign(this.data,patch);},
    CompleteGeneration:definition.CompleteGeneration,
    RefreshResults:vi.fn(),
  };
  await definition.StartGeneration.call(context,true);
  expect(waitTask).toHaveBeenCalledWith('original-task',expect.any(Function));
  expect(request).toHaveBeenCalledTimes(2);
  expect(request).toHaveBeenNthCalledWith(1,'/sessions/original-session');
  expect(request).toHaveBeenNthCalledWith(2,'/me/quota');
  expect(context.data.task.id).toBe('original-task');
  expect(context.data.busy).toBe(false);
});
