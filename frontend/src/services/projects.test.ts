import {beforeEach,expect,test,vi} from 'vitest';
vi.mock('./local-store',()=>({AccountId:()=> 'account',EnsureAccount:vi.fn(),Info:vi.fn(),Get:vi.fn(),Set:vi.fn()}));
vi.mock('./api',()=>({request:vi.fn()}));
vi.mock('./sync',()=>({flushQueue:vi.fn()}));
vi.mock('../engine/tracker',()=>({getActiveTrack:vi.fn(),syncTrack:vi.fn(),localNode:vi.fn(),updateLocalNode:vi.fn()}));
import * as store from './local-store';
import {request} from './api';
import {getActiveTrack,syncTrack} from '../engine/tracker';
import {deleteProject} from './projects';
beforeEach(()=>{vi.resetAllMocks();vi.mocked(store.Info).mockReturnValue({keys:[]} as any);});
test('recording projects cannot be deleted',async()=>{
  vi.mocked(getActiveTrack).mockReturnValue({id:'t',project_id:'p',status:'paused'} as any);
  await expect(deleteProject('p')).rejects.toThrow('先结束');expect(request).not.toHaveBeenCalled();
});
test('unsynced archived tracks block deletion',async()=>{
  vi.mocked(store.Info).mockReturnValue({keys:['nature:track-local:old']} as any);
  vi.mocked(store.Get).mockReturnValue({id:'old',project_id:'p',status:'ended',points:[],nodes:[]});
  await expect(deleteProject('p')).rejects.toThrow('未同步');expect(request).not.toHaveBeenCalled();
});
test('finishes syncing the active ended track and clears only the deleted current project',async()=>{
  const track:any={id:'t',project_id:'p',status:'ended',points:[],nodes:[],uploaded:0};
  vi.mocked(getActiveTrack).mockReturnValue(track);
  vi.mocked(store.Info).mockReturnValue({keys:['nature:track-local:t']} as any);
  vi.mocked(store.Get).mockImplementation(key=>key==='nature:currentProject'?'p':key.startsWith('nature:track-local:')?{...track}:undefined);
  vi.mocked(syncTrack).mockImplementation(async()=>{track.remote_id='remote';});
  await deleteProject('p');
  expect(syncTrack).toHaveBeenCalledOnce();expect(request).toHaveBeenCalledWith('/projects/p','DELETE');expect(store.Set).toHaveBeenCalledWith('nature:currentProject','');
});

test('persisted point batches block deletion even when the local uploaded index has advanced',async()=>{
  const track={id:'old',remote_id:'remote',project_id:'p',status:'ended',points:[],nodes:[],uploaded:0};
  vi.mocked(store.Info).mockReturnValue({keys:['nature:track-local:old']} as any);
  vi.mocked(store.Get).mockImplementation(key=>key==='nature:trackQueue'?[{trackId:'remote'}]:key==='nature:track-local:old'?track:undefined);
  await expect(deleteProject('p')).rejects.toThrow('未同步');expect(request).not.toHaveBeenCalled();
});
test('unsynced cloud node edits block deletion of their project',async()=>{
  vi.mocked(store.Info).mockReturnValue({keys:['nature:node-pending:n']} as any);
  vi.mocked(store.Get).mockImplementation(key=>key==='nature:node-pending:n'?{project_id:'p',text:'未同步的发现'}:undefined);
  await expect(deleteProject('p')).rejects.toThrow('未同步');expect(request).not.toHaveBeenCalled();
});
