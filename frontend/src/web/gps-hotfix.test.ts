import { beforeEach, afterEach, expect, test, vi } from 'vitest';

const fixture=vi.hoisted(()=>({values:new Map<string,any>(),confirm:true}));
vi.mock('../services/local-store',()=>({
  AccountId:()=> 'gps-hotfix-account',EnsureAccount:vi.fn(),
  Get:(key:string)=>fixture.values.get(key),Set:(key:string,value:any)=>fixture.values.set(key,structuredClone(value)),
  Remove:(key:string)=>fixture.values.delete(key),Info:()=>({keys:[...fixture.values.keys()]}),
}));
vi.mock('../services/api',()=>({request:vi.fn().mockResolvedValue({id:'remote-track'}),errorMessage:(error:Error)=>error.message,ApiError:class extends Error{status=0;}}));
vi.mock('../services/sync',()=>({queueTrackPoints:vi.fn(),flushQueue:vi.fn().mockResolvedValue(undefined),loadProject:vi.fn().mockResolvedValue({title:'新笔记'}),persistPhoto:vi.fn()}));
vi.mock('../services/projects',()=>({currentProjectId:()=> 'new-project',chooseProject:vi.fn(),setCurrentProject:vi.fn()}));
vi.mock('../services/workspace',()=>({workspace:{}}));

function BuildTrack(projectId='old-project'){
  return {id:'local-track-test',remote_id:'remote-track',project_id:projectId,title:'旧笔记',status:'recording',points:[],nodes:[],segment:0,uploaded:0,seconds:12,started_at:Date.now(),background:false};
}
function BuildPage(definition:any){
  return {...definition,data:structuredClone(definition.data),setData(patch:any){Object.assign(this.data,patch);}};
}
async function OpenDraft(){
  fixture.values.set('nature:gps:active',BuildTrack());
  const {default:definition}=await import('../pages/node/logic');
  const page=BuildPage(definition);
  await page.onLoad({id:'draft-node',draft:'1',project_id:'old-project',track_id:'local-track-test',latitude:'31.2',longitude:'121.4'});
  return page;
}
beforeEach(()=>{
  vi.resetModules();fixture.values.clear();fixture.confirm=true;vi.clearAllMocks();
  vi.stubGlobal('wx',{
    stopLocationUpdate:vi.fn(),getSystemInfoSync:()=>({statusBarHeight:0}),
    showModal:(options:any)=>options.success({confirm:fixture.confirm,cancel:!fixture.confirm}),
    showToast:vi.fn(),navigateBack:vi.fn(),navigateTo:vi.fn(),
    authorize:(options:any)=>options.success(),startLocationUpdateBackground:(options:any)=>options.success(),
    onLocationChange:vi.fn(),getLocation:vi.fn((options:any)=>options.success({latitude:31.2,longitude:121.4,accuracy:10,timestamp:Date.now()})),
  });
});
afterEach(()=>vi.unstubAllGlobals());

test('退出后恢复为暂停，显示结束之前轨迹；结束后允许新笔记记录，旧轨迹归档保留',async()=>{
  fixture.values.set('nature:gps:active',BuildTrack());
  const {default:definition}=await import('../pages/gps/logic');
  const tracker=await import('../engine/tracker');
  const page=BuildPage(definition);
  await page.onLoad({projectId:'new-project'});
  expect(page.data.hasPreviousTrack).toBe(true);expect(page.data.otherTrack).toBe(true);
  expect(tracker.getActiveTrack()?.status).toBe('paused');
  await page.end();page.onUnload();
  expect(page.data.hasPreviousTrack).toBe(false);expect(page.data.status).toBe('idle');
  expect(fixture.values.get('nature:track-local:local-track-test').status).toBe('ended');
  await page.start();expect(tracker.getActiveTrack()?.project_id).toBe('new-project');
});
test('取消结束旧轨迹后保留记录，按钮不锁死',async()=>{
  fixture.values.set('nature:gps:active',BuildTrack());fixture.confirm=false;
  const {default:definition}=await import('../pages/gps/logic');
  const page=BuildPage(definition);await page.onLoad({projectId:'new-project'});
  await page.end();page.onUnload();expect(page.data.busy).toBe(false);expect(page.data.hasPreviousTrack).toBe(true);
  expect(fixture.values.get('nature:gps:active').status).toBe('paused');
});
test('同一本笔记刷新后也能结束之前轨迹',async()=>{
  fixture.values.set('nature:gps:active',BuildTrack());
  const {default:definition}=await import('../pages/gps/logic');
  const page=BuildPage(definition);await page.onLoad({projectId:'old-project'});
  expect(page.data.hasPreviousTrack).toBe(true);await page.end();page.onUnload();expect(page.data.status).toBe('ended');
});
test('点击添加立即打开草稿，不等待定位、不创建本地点或远端节点',async()=>{
  fixture.values.set('nature:gps:active',BuildTrack());
  const {default:definition}=await import('../pages/gps/logic');
  const {request}=await import('../services/api');
  const page=BuildPage(definition);await page.onLoad({projectId:'old-project'});
  await page.AddNode();page.onUnload();expect(wx.navigateTo).toHaveBeenCalledWith({url:expect.stringContaining('draft=1')});
  expect(fixture.values.get('nature:gps:active').nodes).toHaveLength(0);expect(request).not.toHaveBeenCalled();
  expect(wx.getLocation).not.toHaveBeenCalled();
});

test('定位失败时可以编辑但不能保存，离开后的回调不污染下一份草稿',async()=>{
  let resolveLocation:any;
  vi.mocked(wx.getLocation).mockImplementation((options:any)=>{resolveLocation=options.success;});
  const page=await OpenDraft();
  expect(page.data.loading).toBe(false);expect(page.data.locating).toBe(true);
  page.textInput({detail:{value:'先记录文字'}});await page.save();
  expect(fixture.values.get('nature:gps:active').nodes).toHaveLength(0);
  page.onUnload();page.unloaded=true;
  resolveLocation({latitude:31.2,longitude:121.4,accuracy:10,timestamp:Date.now()});
  await Promise.resolve();await Promise.resolve();
  expect(page.data.hasCoordinates).toBe(false);
});

test('近期可靠轨迹位置直接用于草稿，无需额外定位',async()=>{
  const track=BuildTrack();
  (track.points as any[]).push({latitude:31.2,longitude:121.4,accuracy:10,timestamp:new Date().toISOString()});
  fixture.values.set('nature:gps:active',track);
  const {default:definition}=await import('../pages/node/logic');
  const page=BuildPage(definition);
  await page.onLoad({id:'recent-node',draft:'1',project_id:'old-project',track_id:track.id});
  expect(page.data.hasCoordinates).toBe(true);expect(wx.getLocation).not.toHaveBeenCalled();
});
test('打开并放弃有文字的草稿，不生成观察点或待同步节点',async()=>{
  const page=await OpenDraft();page.textInput({detail:{value:'尚未保存的发现'}});
  await page.back();page.onUnload();
  expect(fixture.values.get('nature:gps:active').nodes).toHaveLength(0);
  expect(fixture.values.has('nature:node:draft-node')).toBe(false);
  expect(fixture.values.has('nature:node-pending:draft-node')).toBe(false);
});
test('仅点击保存创建一次；刷新已保存的草稿地址不重复生成',async()=>{
  const page=await OpenDraft();page.textInput({detail:{value:'热补丁观察'}});
  await page.save();await page.save();
  expect(fixture.values.get('nature:gps:active').nodes).toHaveLength(1);
  expect(fixture.values.get('nature:gps:active').nodes[0].text).toBe('热补丁观察');
  const {default:definition}=await import('../pages/node/logic');
  const reopened=BuildPage(definition);await reopened.onLoad({id:'draft-node',draft:'1',project_id:'old-project'});
  expect(reopened.data.isDraft).toBe(false);expect(reopened.data.text).toBe('热补丁观察');
});
test('草稿的离线照片只在保存后进入观察点同步队列',async()=>{
  const page=await OpenDraft();fixture.values.set('nature:node-draft-uploads:draft-node',['photo-operation']);
  const {syncTrack}=await import('../engine/tracker');await syncTrack();
  expect(fixture.values.get('nature:gps:active').nodes).toHaveLength(0);
  await page.save();
  expect(fixture.values.get('nature:node-uploads:draft-node')).toEqual(['photo-operation']);
  expect(fixture.values.has('nature:node-draft-uploads:draft-node')).toBe(false);
});
test('编辑期间原轨迹结束，拒绝把草稿写进另一条轨迹',async()=>{
  const page=await OpenDraft();const tracker=await import('../engine/tracker');await tracker.endTrack();
  await page.save();expect(page.data.isDraft).toBe(true);expect(page.data.saving).toBe(false);
  expect(page.data.error).toContain('原轨迹已结束');expect(tracker.getActiveTrack()?.nodes).toHaveLength(0);
});
