import {request} from '../../services/api';
import {setCurrentProject,currentProjectId} from '../../services/projects';
import {fail,go,confirm} from '../../components/flows';
export default {
 data:{items:[],loading:true,error:'',title:'',showCreate:false,current:'',saving:false},
 onShow(){this.setData({current:currentProjectId()});this.load();},
 async load(){this.setData({loading:true,error:''});try{const r:any=await request('/projects');this.setData({items:r.items||[]});}catch(e){this.setData({error:(e as Error).message});}finally{this.setData({loading:false});}},
 Open(event:any){
  const projectId=event.currentTarget.dataset.id,project=this.data.items.find(item=>item.id===projectId);
  console.log('[开始] 笔记打开方式');
  if(project?.layout.designMode==='manual'){console.log('[分支] 独立手动设计');go('/pages/design/index?projectId='+projectId);}
  else{console.log('[分支] 观察笔记');setCurrentProject(projectId);go('/pages/canvas/index?projectId='+projectId);}
  console.log('[结束] 笔记打开方式');
 },
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
  console.log('[开始] 笔记删除确认');
  if(!await confirm('删除笔记项目','删除项目不会删除素材库中的原始图片。')){console.log('[分支] 取消；[结束] 笔记删除确认；提前返回');return;}
  console.log('[分支] 删除当前选择的笔记；[结束] 笔记删除确认');
  const projectId=e.currentTarget.dataset.id;
  await request('/projects/'+projectId,'DELETE').then(async()=>{
   console.log('[开始] 当前笔记关联清理');
   if(currentProjectId()===projectId){console.log('[分支] 清除已删除的当前笔记');setCurrentProject('');this.setData({current:''});}
   else{console.log('[分支] 保留其他当前笔记');}
   console.log('[结束] 当前笔记关联清理');await this.load();
  },fail);
 }
};
