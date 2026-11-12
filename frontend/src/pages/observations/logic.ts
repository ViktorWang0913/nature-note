import projects from '../projects/logic';
import {request} from '../../services/api';
import {setCurrentProject,currentProjectId} from '../../services/projects';
import {go} from '../../components/flows';
export default {
  ...projects,
  data:{...projects.data,next:'',loading:false,items:[],error:''},
  onShow(){this.setData({current:currentProjectId()});this.load();},
  async load(){return this.Read(false);},
  async More(){if(this.data.next&&!this.data.loading)return this.Read(true);},
  async Read(append:boolean){
    if(this.data.loading)return;
    this.setData({loading:true,error:''});
    try{
      const items=append?[...this.data.items]:[];let cursor=append?this.data.next:'',found=false;
      do{
        const response=await request('/projects?limit=30'+(cursor?'&cursor='+encodeURIComponent(cursor):''));
        const observations=response.items.filter(item=>item.layout.designMode!=='manual');
        items.push(...observations);found=observations.length>0;cursor=response.next_cursor||'';
      }while(cursor&&!found);
      if(!this.unloaded)this.setData({items,next:cursor});
    }catch(error){this.setData({error:(error as Error).message});}
    finally{this.setData({loading:false});}
  },
  Continue(event:any){const id=event.currentTarget.dataset.id;setCurrentProject(id);go('/pages/gps/index?projectId='+id);},
};
