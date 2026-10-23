import * as localStore from './../../services/local-store';
import {request} from '../../services/api';
import {fail,go,query} from '../../components/flows';
function notificationView(n:any){return {...n,time:(n.created_at||'').replace('T',' ').slice(5,16),isRead:n.read??n.is_read};}
export default {
 data:{filter:'all',q:'',searchOpen:false,items:[],loading:true,error:'',next:''},
 onLoad(){this.load();},
 async load(){this.setData({loading:true,error:''});try{const r:any=await request('/notifications?'+query({filter:this.data.filter,q:this.data.q}));this.setData({items:(r.items||[]).map(notificationView),next:r.next_cursor||''});}catch(e){this.setData({error:(e as Error).message});}finally{this.setData({loading:false});}},
 filter(e:any){this.setData({filter:e.currentTarget.dataset.filter});this.load();},
 search(){this.setData({searchOpen:!this.data.searchOpen});},input(e:any){this.setData({q:e.detail.value});},
 tab(e:any){localStore.Set('communityFeed',e.currentTarget.dataset.feed);wx.switchTab({url:'/pages/community/index'});},
 async open(e:any){try{const n:any=this.data.items.find((x:any)=>x.id===e.currentTarget.dataset.id);await request('/notifications/'+n.id+'/read','POST');this.setData({items:this.data.items.map((x:any)=>x.id===n.id?{...x,isRead:true}:x)});if(['feedback','correction'].includes(n.target_type)){go('/pages/support/index');}else if(n.target_type==='account'){go('/pages/profile/index');}else if(n.target_type==='task'){const task:any=await request('/tasks/'+n.target_id);if(task.kind==='rag'){go('/pages/chat/index');}else{localStore.Set('galleryTab','ai');wx.switchTab({url:'/pages/gallery/index'});}}else if(n.target_type==='user'||n.type==='follow')go('/pages/user/index?id='+(n.actor?.id||n.actor_id||n.target_id));else if(n.target_id)go('/pages/post/index?id='+n.target_id);else wx.showToast({title:'对应内容已不可用',icon:'none'});}catch(e){fail(e);}},
 async more(){try{const r:any=await request('/notifications?'+query({filter:this.data.filter,q:this.data.q,cursor:this.data.next}));this.setData({items:[...this.data.items,...(r.items||[]).map(notificationView)],next:r.next_cursor||''});}catch(e){fail(e);}}
};
