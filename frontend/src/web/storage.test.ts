import { expect, test, vi } from 'vitest';

// 参数设置：延迟数据库打开，覆盖切换账号时的真实异步边界。
const storageMock=vi.hoisted(()=>{
  let ResolveDatabase:(value:unknown)=>void=()=>{};
  const ready=new Promise(resolve=>{ResolveDatabase=resolve;});
  return {ready,ResolveDatabase,put:vi.fn().mockResolvedValue(undefined),get:vi.fn().mockResolvedValue(undefined)};
});
vi.mock('idb',()=>({openDB:()=>storageMock.ready}));
import { ReadFile, WriteFile, WriteValue, FlushStorage } from './storage';

// 主程序
test('pending photo reads and writes retain the originating account',async()=>{
  WriteValue('nature:user',{id:'account-a'});
  const photoBlob=new Blob(['photo']),writeResult=WriteFile('photo',photoBlob),readResult=ReadFile('photo');
  WriteValue('nature:user',{id:'account-b'});
  storageMock.ResolveDatabase({put:storageMock.put,get:storageMock.get});
  await Promise.all([writeResult,readResult,FlushStorage()]);
  expect(storageMock.put).toHaveBeenCalledWith('files',photoBlob,'account-a:photo');
  expect(storageMock.get).toHaveBeenCalledWith('files','account-a:photo');
  expect(storageMock.put).not.toHaveBeenCalledWith('files',photoBlob,'account-b:photo');
});
