import {request} from './api';
import {confirm} from '../components/flows';

// 主程序：共享删除确认和接口，避免素材库与详情页使用不同规则。
export async function DeleteMaterial(asset:any):Promise<boolean>{
  const message=asset.editable===false
    ?'从你的素材库移除此公共素材，不影响其他用户和已保存的笔记。'
    :'从素材库和个人图鉴移除，已保存的笔记保留引用。此操作不能撤销。';
  const accepted=await confirm('删除素材',message);
  console.log('[开始] 素材删除确认');
  if(!accepted){console.log('[分支] 已取消；[结束] 素材删除确认，提前结束');return false;}
  console.log('[分支] 删除选中素材；[结束] 素材删除确认');
  await request('/assets/'+asset.id,'DELETE');return true;
}
