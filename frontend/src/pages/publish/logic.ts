import {request} from '../../services/api';
import {fail,go,decorateAsset,operation,preview} from '../../components/flows';
export default {
 data:{title:'',text:'',location:'',assetIds:[],assets:[],projectId:'',saving:false,error:'',picker:false,choices:[],operationId:''},
 async onLoad(o:any){const ids=(o.assetIds||o.assetId||'').split(',').filter(Boolean);this.setData({assetIds:ids,projectId:o.projectId||'',operationId:operation()});try{const assets=await Promise.all(ids.map(async(id:string)=>decorateAsset(await request('/assets/'+id))));this.setData({assets});}catch(e){fail(e);}},
 input(e:any){this.setData({[e.currentTarget.dataset.field]:e.detail.value});},
 async choose(){try{const r:any=await request('/assets?source=all');this.setData({choices:r.items.filter((x:any)=>x.source!=='public').map(decorateAsset),picker:true});}catch(e){fail(e);}},
 add(e:any){const a:any=this.data.choices.find((x:any)=>x.id===e.currentTarget.dataset.id);if(this.data.assetIds.includes(a.id as never))return;if(this.data.assets.length>=9){wx.showToast({title:'最多选择 9 张图片',icon:'none'});return;}this.setData({assets:[...this.data.assets,a],assetIds:[...this.data.assetIds,a.id],picker:false});},
 remove(e:any){const id=e.currentTarget.dataset.id;this.setData({assets:this.data.assets.filter((x:any)=>x.id!==id),assetIds:this.data.assetIds.filter(x=>x!==id)});},
 close(){this.setData({picker:false});},noop(){},preview(e:any){preview(e.currentTarget.dataset.url);},
 async publish(){if(this.data.saving)return;if(!this.data.title.trim()||!this.data.assetIds.length){wx.showToast({title:'请填写标题并选择图片',icon:'none'});return;}this.setData({saving:true,error:''});try{const p:any=await request('/posts','POST',{title:this.data.title.trim(),text:this.data.text,location_text:this.data.location,asset_ids:this.data.assetIds,project_id:this.data.projectId||undefined,operation_id:this.data.operationId});wx.redirectTo({url:'/pages/post/index?id='+p.id});}catch(e){this.setData({error:(e as Error).message});fail(e);}finally{this.setData({saving:false});}}
};
