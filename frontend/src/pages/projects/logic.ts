import {request} from '../../services/api';
import {setCurrentProject,currentProjectId,deleteProject} from '../../services/projects';
import {fail,go,confirm} from '../../components/flows';
export default {
 data:{items:[],next:'',loading:false,error:'',title:'',showCreate:false,current:'',saving:false,removingId:''},
 onShow(){this.setData({current:currentProjectId()});this.load();},
 async load(){return this.Read(false);},
 async More(){if(this.data.next&&!this.data.loading)return this.Read(true);},
 async Read(append:boolean){
  if(this.data.loading)return;
  this.setData({loading:true,error:''});
  try{const result=await request('/projects'+(append?'?cursor='+encodeURIComponent(this.data.next):''));if(!this.unloaded)this.setData({items:append?[...this.data.items,...result.items]:result.items,next:result.next_cursor||''});}
  catch(error){this.setData({error:(error as Error).message});}
  finally{this.setData({loading:false});}
 },
 Open(event:any){
  const projectId=event.currentTarget.dataset.id,project=this.data.items.find(item=>item.id===projectId);
  console.log('[开始] 笔记打开方式');
  if(project?.layout.designMode==='manual'){console.log('[分支] 独立手动设计');go('/pages/design/index?projectId='+projectId);}
  else{console.log('[分支] 观察笔记');setCurrentProject(projectId);go('/pages/canvas/index?projectId='+projectId);}
  console.log('[结束] 笔记打开方式');
 },
 NewDesign(){go('/pages/design/index');},
 create(){this.setData({showCreate:true,title:''});},close(){this.setData({showCreate:false});},noop(){},input(e:any){this.setData({title:e.detail.value});},
 async save(){
  console.log('[开始] 创建笔记重复提交检查');
  if(this.data.saving){console.log('[分支] 正在保存；[结束] 创建笔记重复提交检查；提前返回');return;}
  console.log('[分支] 创建一次；[结束] 创建笔记重复提交检查');
  this.setData({saving:true});
  await request<any>('/projects','POST',{title:this.data.title.trim()||'自然观察 '+new Date().toLocaleDateString('zh-CN')}).then(project=>{
   setCurrentProject(project.id);this.setData({showCreate:false});go('/pages/gps/index?projectId='+project.id);
  },fail).finally(()=>this.setData({saving:false}));
 },
 async remove(e:any){
  if(this.data.removingId)return;
  const id=e.currentTarget.dataset.id;this.setData({removingId:id});
  try{
   if(!await confirm('删除笔记项目','项目将从列表移除，原始轨迹和观察点会解除项目关联，素材库中的原始图片保留。'))return;
   await deleteProject(id);this.setData({current:currentProjectId()});await this.load();
  }catch(error){fail(error);}
  finally{this.setData({removingId:''});}
 }
};
