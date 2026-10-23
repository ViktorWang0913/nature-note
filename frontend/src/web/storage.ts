import { openDB } from 'idb';

// 参数设置：业务键按账号分区，照片不占用 localStorage。
const database = openDB('nature-note-web',1,{upgrade(database){database.createObjectStore('values');database.createObjectStore('files');}});
const values=new Map<string,any>();
let pendingWrites:Promise<unknown>=Promise.resolve();

export async function InitializeStorage(){
  const storage=await database,keys=await storage.getAllKeys('values'),records=await storage.getAll('values');
  console.log(`[开始] 本机缓存读取，共 ${keys.length} 项`);
  keys.forEach((key,index)=>{console.log(`[开始] 缓存 ${index+1}/${keys.length}`);values.set(String(key),records[index]);console.log(`[结束] 缓存 ${index+1}/${keys.length}`);});console.log('[结束] 本机缓存读取');
}
export function ReadValue(key:string){return values.get(key);}
export function WriteValue(key:string,value:any){
  const snapshot=JSON.parse(JSON.stringify(value));values.set(key,snapshot);
  pendingWrites=pendingWrites.then(async()=>{await (await database).put('values',snapshot,key);});
  pendingWrites.then(undefined,error=>window.dispatchEvent(new CustomEvent('nature-storage-error',{detail:error.message})));
}
export function RemoveValue(key:string){values.delete(key);pendingWrites=pendingWrites.then(async()=>{await (await database).delete('values',key);});}
export function StorageInfo(){return {keys:[...values.keys()],currentSize:Math.ceil(JSON.stringify([...values]).length/1024),limitSize:0};}
export async function FlushStorage(){await pendingWrites;}
export function CurrentAccount(){return ReadValue('nature:user')?.id||'';}
export async function WriteFile(key:string,blob:Blob){const accountKey=CurrentAccount()+':'+key;await (await database).put('files',blob,accountKey);}
export async function ReadFile(key:string):Promise<Blob|undefined>{const accountKey=CurrentAccount()+':'+key;return (await database).get('files',accountKey);}
