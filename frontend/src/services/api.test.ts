import { beforeEach, expect, test, vi } from 'vitest';

const accountMock=vi.hoisted(()=>({id:'account-a'}));
vi.mock('./local-store',()=>({
  AccountId:()=>accountMock.id,
  EnsureAccount:(accountId:string)=>{
    console.log('[开始] 测试账号边界');
    if(accountId!==accountMock.id){console.log('[分支] 已切换；[结束] 测试账号边界');throw new Error('账号已切换');}
    console.log('[分支] 同一账号；[结束] 测试账号边界');
  },
  Remove:vi.fn(),Set:vi.fn()
}));
vi.mock('../web/auth',()=>({authState:{user:{id:'account-a'}},authEpoch:0,LogoutSession:vi.fn(),ApiError:class extends Error{constructor(public status:number,public code:string,message:string){super(message);}}}));
vi.mock('../web/media',()=>({ReadBlob:vi.fn()}));
vi.mock('../web/storage',()=>({FlushStorage:vi.fn()}));
import { request } from './api';

beforeEach(()=>{accountMock.id='account-a';vi.stubGlobal('fetch',vi.fn());});

test('account switch before request dispatch prevents sending old payload',async()=>{
  const pending=request('/tracks','POST',{title:'old-account-track'});
  accountMock.id='account-b';
  await expect(pending).rejects.toThrow('账号已切换');
  expect(fetch).not.toHaveBeenCalled();
});

test('late response from old account is rejected',async()=>{
  let ResolveResponse:(value:Response)=>void=()=>{};
  vi.mocked(fetch).mockReturnValue(new Promise(resolve=>{ResolveResponse=resolve;}));
  const pending=request('/assets');
  await Promise.resolve();
  expect(fetch).toHaveBeenCalledOnce();
  accountMock.id='account-b';
  ResolveResponse(new Response(JSON.stringify({items:[{id:'old-private-image'}]}),{status:200}));
  await expect(pending).rejects.toThrow('账号已切换');
});
