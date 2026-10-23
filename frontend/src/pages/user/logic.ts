import {request} from '../../services/api';import {fail,go,query} from '../../components/flows';
export default {
 data:{id:'',user:null,me:'',posts:[],loading:true,error:''},
 onLoad(o:any){this.setData({id:o.id});this.load();},
 async load(){this.setData({loading:true,error:''});try{const [u,p,m]:any[]=await Promise.all([request('/users/'+this.data.id),request('/posts?'+query({user_id:this.data.id})),request('/me')]);this.setData({user:u,me:m.id,posts:p.items.map((x:any)=>({...x,cover:x.cover_url||x.images?.[0]?.url||x.images?.[0]||x.image_urls?.[0]}))});}catch(e){this.setData({error:(e as Error).message});}finally{this.setData({loading:false});}},
 async follow(){try{const u:any=this.data.user;const r:any=await request('/users/'+u.id+'/follow','PUT',{following:!u.following});this.setData({user:{...u,following:r.following??!u.following}});}catch(e){fail(e);}},
 open(e:any){go('/pages/post/index?id='+e.currentTarget.dataset.id);},profile(){go('/pages/profile/index');}
};
