import {request} from '../../services/api';
import {fail,go,preview,confirm} from '../../components/flows';
export default {
 data:{id:'',loading:true,error:'',post:null,comments:[],comment:'',userId:'',sending:false,images:[]},
 onLoad(o:any){this.setData({id:o.id});this.load();},
 async load(){this.setData({loading:true,error:''});try{const [p,c,u]:any[]=await Promise.all([request('/posts/'+this.data.id),request('/posts/'+this.data.id+'/comments'),request('/me')]);const images=(p.images||p.image_urls||p.assets||[]).map((x:any)=>typeof x==='string'?x:x.url||x.image_url);this.setData({post:{...p,author:p.author||{id:p.user_id,nickname:p.author_name||'自然观察者'}},comments:c.items||[],userId:u.id,images});}catch(e){this.setData({error:(e as Error).message});}finally{this.setData({loading:false});}},
 preview(e:any){preview(e.currentTarget.dataset.url,this.data.images);},author(e:any){go('/pages/user/index?id='+e.currentTarget.dataset.id);},
 input(e:any){this.setData({comment:e.detail.value});},
 async send(){if(!this.data.comment.trim()||this.data.sending)return;this.setData({sending:true});try{await request('/posts/'+this.data.id+'/comments','POST',{text:this.data.comment.trim()});this.setData({comment:''});const r:any=await request('/posts/'+this.data.id+'/comments');this.setData({comments:r.items});}catch(e){fail(e);}finally{this.setData({sending:false});}},
 async like(){try{const p:any=this.data.post;const r:any=await request('/posts/'+p.id+'/like','PUT',{liked:!p.liked});this.setData({post:{...p,liked:r.liked??!p.liked,like_count:r.like_count??((p.like_count||0)+(p.liked?-1:1))}});}catch(e){fail(e);}},
 async remove(){if(!await confirm('撤回这篇分享','公开帖子和相关互动将不再显示，私人笔记仍保留。'))return;try{await request('/posts/'+this.data.id,'DELETE');wx.navigateBack();}catch(e){fail(e);}},
 async removeComment(e:any){if(!await confirm('删除评论','确认删除这条评论？'))return;try{await request('/comments/'+e.currentTarget.dataset.id,'DELETE');this.setData({comments:this.data.comments.filter((x:any)=>x.id!==e.currentTarget.dataset.id)});}catch(e){fail(e);}},
 async report(){const r:any=await new Promise(resolve=>wx.showActionSheet({itemList:['内容与自然观察无关','不当言论','图片或资料侵权','其他'],success:resolve}));try{await request('/reports','POST',{target_type:'post',target_id:this.data.id,reason:['内容与自然观察无关','不当言论','图片或资料侵权','其他'][r.tapIndex]});wx.showToast({title:'已提交举报'});}catch(e){fail(e);}}
};
