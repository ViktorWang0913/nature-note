import {request} from '../../services/api';
import {fail,go,pickPhoto,selectTab,query} from '../../components/flows';
export default {
 data:{loading:true,error:'',q:'',resultQuery:'',resultSort:'category',sort:'category',items:[],total:null as number|null,next:''},
 _loadEpoch:0,
 onShow(){selectTab(2);this.load();},
 async load(){
  const epoch=++this._loadEpoch,q=this.data.q.trim(),sort=this.data.sort;this.setData({loading:true,error:''});
  try{const result=await request('/atlas?'+query({q,sort}));if(epoch===this._loadEpoch&&!this.unloaded)this.setData({items:result.items,total:Number.isInteger(result.total)?result.total:null,resultQuery:q,resultSort:sort,next:result.next_cursor||''});}
  catch(error){if(epoch===this._loadEpoch)this.setData({error:(error as Error).message});}
  finally{if(epoch===this._loadEpoch)this.setData({loading:false});}
 },
 input(e:any){this.setData({q:e.detail.value});},sort(e:any){this.setData({sort:e.currentTarget.dataset.sort});return this.load();},
 species(e:any){go('/pages/species/index?id='+e.currentTarget.dataset.id);},
 async import(){try{const a=await pickPhoto();go('/pages/asset/index?id='+a.id+'&recognize=1');}catch(e){if(!(e as any).errMsg?.includes('cancel'))fail(e);}},
 async more(){
  if(this.data.loading||!this.data.next)return;
  const epoch=this._loadEpoch;this.setData({loading:true});
  try{const result=await request('/atlas?'+query({q:this.data.resultQuery,sort:this.data.resultSort,cursor:this.data.next}));if(epoch===this._loadEpoch&&!this.unloaded)this.setData({items:[...this.data.items,...result.items],next:result.next_cursor||''});}
  catch(error){if(epoch===this._loadEpoch)fail(error);}
  finally{if(epoch===this._loadEpoch)this.setData({loading:false});}
 }
};
