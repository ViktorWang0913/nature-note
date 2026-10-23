import * as localStore from './../../services/local-store';
import {request,ensureLogin,RegisterAgain} from '../../services/api';
import {pendingPhotoCount,flushQueue} from '../../services/sync';
import {syncTrack} from '../../engine/tracker';
import {setCurrentProject,chooseProject,importAsset} from '../../services/projects';
import {fail,go,pickPhoto,selectTab} from '../../components/flows';
export default {
 data:{loading:true,error:'',templates:[],photo:'',illustration:'',pending:0,signedOut:false,signingIn:false},
 onShow(){selectTab(0);const signedOut=!!localStore.Get('nature:signedOut');this.setData({signedOut,pending:pendingPhotoCount()});if(!signedOut)this.load();},
 async signIn(){this.setData({signingIn:true});try{await ensureLogin(true).then(value=>value,error=>{console.log('[开始] 登录异常分派');if(error.code==='account_deleted'){console.log('[分支] 请求空白新账号确认');console.log('[结束] 登录异常分派');return RegisterAgain();}console.log('[分支] 保留登录错误');console.log('[结束] 登录异常分派');throw error;});this.setData({signedOut:false});await this.load();flushQueue().then(()=>syncTrack()).catch(()=>{});}catch(e){localStore.Set('nature:signedOut',true);fail(e);}finally{this.setData({signingIn:false});}},
 async load(){this.setData({loading:true,error:''});try{const [templates,featured]:any[]=await Promise.all([request('/templates?limit=2'),request('/assets/featured')]);this.setData({templates:templates.items||[],photo:featured.photo,illustration:featured.illustration});}catch(e){this.setData({error:(e as Error).message});}finally{this.setData({loading:false});}},
 async Create(){await chooseProject().then(projectId=>go('/pages/gps/index?projectId='+projectId),fail);},
 Design(){go('/pages/design/index');},
 Profile(){go('/pages/profile/index');},
 async camera(){try{const asset=await pickPhoto();go('/pages/asset/index?id='+asset.id);}catch(e){if(!(e as any).errMsg?.includes('cancel'))fail(e);}},
 generate(){localStore.Set('galleryTab','ai');wx.switchTab({url:'/pages/gallery/index'});},
 collage(){go('/pages/projects/index');},
 async gps(){try{const id=await chooseProject();go('/pages/gps/index?projectId='+id);}catch(e){fail(e);}},
 Support(){go('/pages/support/index');},
 Chat(){go('/pages/chat/index');},
 tutorial(){go('/pages/tutorial/index');},
 allTemplates(){localStore.Set('galleryTab','templates');wx.switchTab({url:'/pages/gallery/index'});},
 queued(){localStore.Set('galleryTab','assets');wx.switchTab({url:'/pages/gallery/index'});},
 async useTemplate(e:any){try{const id=await chooseProject();go('/pages/canvas/index?projectId='+id+'&templateId='+e.currentTarget.dataset.id);}catch(e){fail(e);}}
};
