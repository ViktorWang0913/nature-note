import {request} from '../../services/api';
import {fail,go,pickPhoto,selectTab,query} from '../../components/flows';
export default {
 data:{loading:true,error:'',q:'',sort:'category',user:null,items:[],recorded:0,next:''},
 onShow(){selectTab(2);this.load();},
 async load(){this.setData({loading:true,error:''});try{const [u,r]:any[]=await Promise.all([request('/me'),request('/atlas?'+query({q:this.data.q,sort:this.data.sort}))]);this.setData({user:u,items:r.items,recorded:r.items.filter((x:any)=>x.photo_count>0).length,next:r.next_cursor||''});}catch(e){this.setData({error:(e as Error).message});}finally{this.setData({loading:false});}},
 input(e:any){this.setData({q:e.detail.value});},sort(e:any){this.setData({sort:e.currentTarget.dataset.sort});this.load();},
 species(e:any){go('/pages/species/index?id='+e.currentTarget.dataset.id);},profile(){go('/pages/profile/index');},achievements(){go('/pages/profile/index?section=achievements');},
 async import(){try{const a=await pickPhoto();go('/pages/asset/index?id='+a.id+'&recognize=1');}catch(e){if(!(e as any).errMsg?.includes('cancel'))fail(e);}},
 async more(){try{const r:any=await request('/atlas?'+query({q:this.data.q,sort:this.data.sort,cursor:this.data.next}));this.setData({items:[...this.data.items,...r.items],next:r.next_cursor||''});}catch(e){fail(e);}}
};
