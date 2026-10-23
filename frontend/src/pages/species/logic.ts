import * as localStore from './../../services/local-store';
import {persistPhoto,flushQueue} from '../../services/sync';
import {request} from '../../services/api';
import {importAsset} from '../../services/projects';
import {fail,go,query,preview,decorateAsset} from '../../components/flows';
export default {
 data:{next:'',id:'',loading:true,error:'',species:null,photos:[],allPhotos:[],selected:'',showAll:false,knowledge:false,question:'',answer:null,busy:false},
 onLoad(options:any){this.setData({id:options.id});this.load();},
 async load(){this.setData({loading:true,error:''});try{const [s,o]:any[]=await Promise.all([request('/species/'+this.data.id),request('/observations?'+query({species_id:this.data.id,limit:100}))]);const observations=o.items||[];const loaded=await Promise.all(observations.map(async(x:any)=>{const a:any=x.asset||await request('/assets/'+x.asset_id);return {...decorateAsset(a),observation_id:x.id,date:(x.observed_at||x.created_at||'').slice(0,10),note:x.text};}));const photos=loaded.filter((x:any,i:number,arr:any[])=>arr.findIndex(y=>y.id===x.id)===i);this.setData({next:o.next_cursor||'',species:s,photos:photos.slice(0,2),allPhotos:photos,selected:photos[0]?.id||''});}catch(e){this.setData({error:(e as Error).message});}finally{this.setData({loading:false});}},
 select(e:any){this.setData({selected:e.currentTarget.dataset.id});},
 preview(e:any){preview(e.currentTarget.dataset.url);},
 more(){this.setData({showAll:!this.data.showAll,photos:!this.data.showAll?this.data.allPhotos:this.data.allPhotos.slice(0,2)});},
 menu(e:any){go('/pages/asset/index?id='+e.currentTarget.dataset.id);},
 async use(){try{if(!this.data.selected){wx.showToast({title:'请先选择照片',icon:'none'});return;}const id=await importAsset(this.data.selected);go('/pages/canvas/index?projectId='+id);}catch(e){fail(e);}},
 knowledge(){go('/pages/chat/index?species='+encodeURIComponent((this.data.species as any)?.name||''));},
 async LoadMore(){const result:any=await request('/observations?'+query({species_id:this.data.id,limit:100,cursor:this.data.next}));const photos=result.items.map((item:any)=>({...decorateAsset(item.asset),observation_id:item.id,date:(item.observed_at||item.created_at||'').slice(0,10),note:item.text}));const allPhotos=[...this.data.allPhotos,...photos];this.setData({allPhotos,photos:allPhotos,showAll:true,next:result.next_cursor||''});},
 async Add(){
 const choice:any=await new Promise((resolve,reject)=>wx.showActionSheet({itemList:['拍照','相册（最多 9 张）','从我的照片选择'],success:resolve,fail:reject}));
 console.log('[开始] 图鉴添加照片来源');
 if(choice.tapIndex===2){console.log('[分支] 选择已有照片');localStore.Set('atlasTarget',{id:this.data.id,name:(this.data.species as any)?.name});localStore.Set('galleryTab','assets');wx.switchTab({url:'/pages/gallery/index'});console.log('[结束] 图鉴添加照片来源；提前跳转');return;}
 console.log('[分支] 拍摄或导入照片');console.log('[结束] 图鉴添加照片来源');
 const picked:any=await new Promise((resolve,reject)=>wx.chooseMedia({count:choice.tapIndex===0?1:9,mediaType:['image'],sourceType:[choice.tapIndex===0?'camera':'album'],success:resolve,fail:reject}));
 const answer:any=await new Promise(resolve=>wx.showModal({title:'确认归档',content:'将所选照片归入 '+(this.data.species as any)?.name+'，不调用 AI，不消耗额度。',success:resolve}));
 console.log('[开始] 图鉴导入确认');if(!answer.confirm){console.log('[分支] 取消');console.log('[结束] 图鉴导入确认；提前结束');return;}console.log('[分支] 保存并归档');console.log('[结束] 图鉴导入确认');
 const operations:string[]=[];console.log('[开始] 导入照片保存');
 for(let photoIndex=0;photoIndex<picked.tempFiles.length;photoIndex++){console.log(`[开始] 保存照片 ${photoIndex+1}/${picked.tempFiles.length}`);operations.push(await persistPhoto(picked.tempFiles[photoIndex].tempFilePath));console.log(`[结束] 保存照片 ${photoIndex+1}/${picked.tempFiles.length}`);}
 console.log('[结束] 导入照片保存');await flushQueue();const ids=operations.map(id=>localStore.Get('nature:uploaded:'+id)?.id).filter(Boolean);
 await request('/species/'+this.data.id+'/photos','POST',{asset_ids:ids});await this.load();
 },
 async Cover(){console.log('[开始] 图鉴封面选择');if(!this.data.selected){console.log('[分支] 未选照片');console.log('[结束] 图鉴封面选择；提前结束');return;}console.log('[分支] 保存封面');console.log('[结束] 图鉴封面选择');await request('/species/'+this.data.id+'/cover','PUT',{asset_id:this.data.selected});await this.load();}
};
