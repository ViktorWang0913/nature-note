import * as localStore from './../../services/local-store';
import { request, errorMessage, ApiError } from '../../services/api';
import { persistPhoto, flushQueue } from '../../services/sync';
import { Asset } from '../../types/models';
import { localNode, updateLocalNode, getActiveTrack, syncTrack, SaveLocalNode } from '../../engine/tracker';
import { clone } from '../../engine/scene';
import { IsRecentPosition } from '../../engine/observation-location';
let nodeId='',projectId='',node:any=null,dirty=false;
const modal=(o:any):Promise<any>=>new Promise(resolve=>wx.showModal({...o,success:resolve}));
export default {data:{topInset:25,loading:true,saving:false,isDraft:false,locating:false,locationMessage:'',savedMessage:'',error:'',label:'01',timeLabel:'',speciesName:'',latitude:'',longitude:'',hasCoordinates:false,placeName:'',text:'',assets:[] as Asset[],coverId:'',coverUrl:'',pickerOpen:false,library:[] as Asset[],pendingCount:0},
  async onLoad(this:any,options:any){
    nodeId=options.id;projectId=options.project_id||options.projectId||'';node=null;dirty=false;
    this.setData({topInset:wx.getSystemInfoSync().statusBarHeight||25});
    console.log('[开始] 新观察点草稿检查');
    if(options.draft==='1'&&!localNode(nodeId)){
      console.log('[分支] 在编辑页内暂存，尚未写入轨迹');
      const track=getActiveTrack();
      console.log('[开始] 草稿所属轨迹与坐标检查');
      if(!track||track.id!==options.track_id||track.project_id!==projectId||track.status==='ended'){
        console.log('[分支] 草稿不可用；[结束] 草稿所属轨迹与坐标检查；[结束] 新观察点草稿检查；提前结束');
        this.setData({loading:false,error:'原轨迹已结束或位置无效，请返回轨迹重新添加'});return;
      }
      console.log('[分支] 有效草稿；[结束] 草稿所属轨迹与坐标检查');
      node={id:nodeId,project_id:projectId,track_id:track.id,time:options.time||new Date().toISOString(),text:'',asset_ids:[]};
      this.setData({isDraft:true});
    }else{console.log('[分支] 读取已经保存的观察点');}
    console.log('[结束] 新观察点草稿检查');await this.reload();
    console.log('[开始] 草稿位置准备');
    if(this.data.isDraft){console.log('[分支] 后台取得真实位置');this.LocateDraft();}
    else{console.log('[分支] 保留已有观察点位置');}
    console.log('[结束] 草稿位置准备');
  },
  async LocateDraft(this:any){
    console.log('[开始] 草稿定位请求');
    if(this.unloaded||this.data.locating||!this.data.isDraft||!node){console.log('[分支] 无需重复定位；[结束] 草稿定位请求；提前结束');return;}
    console.log('[分支] 检查近期位置；[结束] 草稿定位请求');
    const draft=node,accountId=localStore.AccountId(),track=getActiveTrack(),recent=track?.points.at(-1);
    this.setData({locating:true,locationMessage:'正在定位，你可以先填写观察内容'});
    let position=recent;
    console.log('[开始] 近期定位可用性');
    if(track?.id===draft.track_id&&IsRecentPosition(recent)){console.log('[分支] 使用近期可靠位置');}
    else{
      console.log('[分支] 后台请求定位');
      position=await ReadObservationPosition(false);
      console.log('[开始] 定位精度提升');
      if(!IsRecentPosition(position)&&!this.unloaded&&node===draft&&accountId===localStore.AccountId()){
        console.log('[分支] 后台等待更可靠的位置，输入不受影响');
        this.setData({locationMessage:'正在获取更准确的位置，你可以继续填写'});
        position=await ReadObservationPosition(true);
      }else{console.log('[分支] 已有可靠位置或已离开页面');}
      console.log('[结束] 定位精度提升');
    }
    console.log('[结束] 近期定位可用性');
    console.log('[开始] 定位回调所属草稿');
    if(this.unloaded||node!==draft||accountId!==localStore.AccountId()||!this.data.isDraft){console.log('[分支] 页面或账号已切换，丢弃回调；[结束] 定位回调所属草稿；提前结束');return;}
    console.log('[分支] 当前草稿；[结束] 定位回调所属草稿');
    console.log('[开始] 草稿定位结果');
    if(IsRecentPosition(position)){
      console.log('[分支] 位置可用于此次观察');
      Object.assign(draft,{latitude:position!.latitude,longitude:position!.longitude});
      this.setData({hasCoordinates:true,latitude:position!.latitude.toFixed(6),longitude:position!.longitude.toFixed(6),locationMessage:'位置已就绪 · 精度约 '+Math.round(position!.accuracy)+' 米'});
    }else{
      console.log('[分支] 不使用过期或不可靠的位置');
      this.setData({locationMessage:'暂时无法取得可靠位置，请检查定位权限或移至开阔处后重试'});
    }
    console.log('[结束] 草稿定位结果');this.setData({locating:false});
  },
  onUnload(this:any){
    console.log('[开始] 离开观察点草稿');
    if(this.data.isDraft){console.log('[分支] 丢弃未保存关联，已上传照片仍在素材库');localStore.Remove('nature:node-draft-uploads:'+nodeId);}
    else{console.log('[分支] 保留已保存观察点');}
    console.log('[结束] 离开观察点草稿');
  },
  async onShow(this:any){if(node)await this.resolvePending();},
  async reload(this:any){this.setData({loading:true,error:''});try{const local=localNode(nodeId);if(local)node=clone(local);else if(!this.data.isDraft){try{node=await request<any>('/nodes/'+nodeId);}catch(e){const cache=localStore.Get('nature:node:'+nodeId);if(cache)node=cache;else throw e;}}
    const pending=localStore.Get('nature:node-pending:'+nodeId);if(pending)Object.assign(node,pending);projectId=projectId||node.project_id;
    const assets:Asset[]=[];for(const id of node.asset_ids||[]){try{const asset=await request<Asset>('/assets/'+id);assets.push(asset);localStore.Set('nature:asset:'+id,asset);}catch(_){const cached=localStore.Get('nature:asset:'+id);if(cached)assets.push(cached);}}
    this.setData({loading:false,placeName:node.place_name||'',text:node.text||'',assets,coverId:node.cover_asset_id||assets[0]?.id||'',hasCoordinates:Number.isFinite(node.latitude),latitude:Number(node.latitude||0).toFixed(6),longitude:Number(node.longitude||0).toFixed(6),timeLabel:node.time?new Date(node.time).toLocaleString():'示意节点',label:node.label||'◎'});this.refreshCover();
    console.log('[开始] 观察点缓存写入范围');
    if(!this.data.isDraft){console.log('[分支] 缓存已保存观察点');localStore.Set('nature:node:'+nodeId,node);}
    else{console.log('[分支] 草稿只保留在当前编辑页');}
    console.log('[结束] 观察点缓存写入范围');await this.resolvePending();
  }catch(e){this.setData({loading:false,error:errorMessage(e)});}},
  refreshCover(this:any){this.setData({coverUrl:this.data.assets.find((a:Asset)=>a.id===this.data.coverId)?.url||''});},
  PlaceInput(this:any,event:any){this.setData({placeName:event.detail.value});dirty=true;},
  textInput(this:any,e:any){this.setData({text:e.detail.value});dirty=true;},setCover(this:any,e:any){this.setData({coverId:e.currentTarget.dataset.id});this.refreshCover();dirty=true;},
  removeAsset(this:any,e:any){const assets=this.data.assets.filter((a:Asset)=>a.id!==e.currentTarget.dataset.id);this.setData({assets,coverId:this.data.coverId===e.currentTarget.dataset.id?assets[0]?.id||'':this.data.coverId});this.refreshCover();dirty=true;},
  preview(this:any,e:any){const a=this.data.assets.find((a:Asset)=>a.id===e.currentTarget.dataset.id);if(a)wx.previewImage({current:a.url,urls:this.data.assets.map((a:Asset)=>a.url)});},previewCover(this:any){if(this.data.coverUrl)wx.previewImage({current:this.data.coverUrl,urls:this.data.assets.map((a:Asset)=>a.url)});},
  async chooseAssets(this:any){try{const list=await request<any>('/assets');this.setData({library:list.items,pickerOpen:true});}catch(e){wx.showToast({title:errorMessage(e),icon:'none'});}},closePicker(this:any){this.setData({pickerOpen:false});},
  selectAsset(this:any,e:any){const asset=this.data.library.find((a:Asset)=>a.id===e.currentTarget.dataset.id);if(!asset)return;this.addAsset(asset);wx.showToast({title:'已加入',icon:'success'});},
  addAsset(this:any,asset:Asset){if(this.data.assets.some((a:Asset)=>a.id===asset.id))return;this.setData({assets:[...this.data.assets,asset],coverId:this.data.coverId||asset.id});localStore.Set('nature:asset:'+asset.id,asset);this.refreshCover();dirty=true;},
  async addPhotos(this:any){try{const files:any=await new Promise((resolve,reject)=>wx.chooseMedia({count:9,mediaType:['image'],sourceType:['album','camera'],success:resolve,fail:reject}));const key=(this.data.isDraft?'nature:node-draft-uploads:':'nature:node-uploads:')+nodeId,ops:string[]=localStore.Get(key)||[];for(const file of files.tempFiles)ops.push(await persistPhoto(file.tempFilePath));localStore.Set(key,ops);this.setData({pendingCount:ops.length});dirty=true;await this.resolvePending();}catch(e){if(!errorMessage(e).includes('cancel'))wx.showToast({title:errorMessage(e),icon:'none'});}},
  async resolvePending(this:any){const key=(this.data.isDraft?'nature:node-draft-uploads:':'nature:node-uploads:')+nodeId,ops:string[]=localStore.Get(key)||[];if(!ops.length)return;try{await flushQueue();}catch(_){}const pending:string[]=[];for(const op of ops){const asset=localStore.Get('nature:uploaded:'+op);if(asset)this.addAsset(asset);else pending.push(op);}localStore.Set(key,pending);this.setData({pendingCount:pending.length});},
  async SaveDraft(this:any){
    console.log('[开始] 保存草稿位置检查');
    if(!this.data.hasCoordinates||!Number.isFinite(node?.latitude)||!Number.isFinite(node?.longitude)){
      console.log('[分支] 尚未取得有效位置；[结束] 保存草稿位置检查；提前结束');
      this.setData({locationMessage:'请先取得有效位置，再保存观察点'});return;
    }
    console.log('[分支] 使用此次观察的有效位置；[结束] 保存草稿位置检查');
    this.setData({saving:true,error:''});
    const saved=await Promise.resolve().then(()=>SaveLocalNode({...node,place_name:this.data.placeName,text:this.data.text,asset_ids:this.data.assets.map((asset:Asset)=>asset.id),cover_asset_id:this.data.coverId||undefined})).then(savedNode=>{
      node=savedNode;
      localStore.Set('nature:node:'+nodeId,node);
      localStore.Set('nature:node-uploads:'+nodeId,localStore.Get('nature:node-draft-uploads:'+nodeId)||[]);
      localStore.Remove('nature:node-draft-uploads:'+nodeId);
      dirty=false;this.setData({isDraft:false});
      this.setData({savedMessage:'已保存在本机，正在同步…'});
      return syncTrack().then(()=>{
        console.log('[开始] 并行同步完成检查');
        if(!savedNode.remote_id||savedNode.dirty){console.log('[分支] 补同步刚保存的观察点；[结束] 并行同步完成检查');return syncTrack();}
        console.log('[分支] 观察点已同步；[结束] 并行同步完成检查');
      }).then(()=>{
        console.log('[开始] 观察点保存完成');
        this.setData({savedMessage:'观察记录已保存并同步'});wx.showToast({title:'观察记录已保存',icon:'success'});
        console.log('[结束] 观察点保存完成');
      },error=>this.setData({savedMessage:'已保存在本机，等待同步',error:'观察点已保存在本机，联网后同步：'+errorMessage(error)}));
    },error=>this.setData({error:errorMessage(error)})).finally(()=>this.setData({saving:false}));
    return saved;
  },
  async save(this:any){if(!node||this.data.saving)return;
    console.log('[开始] 观察点保存类型');
    if(this.data.isDraft){console.log('[分支] 首次保存草稿；[结束] 观察点保存类型；转入草稿保存');await this.SaveDraft();return;}
    console.log('[分支] 更新已有观察点；[结束] 观察点保存类型');
    this.setData({saving:true,error:''});const patch={place_name:this.data.placeName,text:this.data.text,asset_ids:this.data.assets.map((a:Asset)=>a.id),cover_asset_id:this.data.coverId||null};try{
    Object.assign(node,patch);localStore.Set('nature:node:'+nodeId,node);
    if(localNode(nodeId)){updateLocalNode(nodeId,patch as any);try{await syncTrack();}catch(_){}}
    else if(!node.layout_only){try{node=await request('/nodes/'+nodeId,'PATCH',patch);localStore.Remove('nature:node-pending:'+nodeId);}catch(e){if(e instanceof ApiError&&e.status===0){localStore.Set('nature:node-pending:'+nodeId,{...patch,project_id:projectId});this.setData({error:'记录已保存在本机，联网后同步'});}else throw e;}}
    dirty=false;wx.showToast({title:'观察记录已保存',icon:'success'});
  }catch(e){this.setData({error:'本机已保留修改：'+errorMessage(e)});}finally{this.setData({saving:false});}},
  async back(this:any){
    console.log('[开始] 离开未保存观察点检查');
    if(this.data.isDraft){
      console.log('[分支] 未保存草稿不会生成观察点；[结束] 离开未保存观察点检查');
      console.log('[开始] 草稿修改检查');
      if(dirty){
        console.log('[分支] 确认放弃草稿');
        const answer=await modal({title:'放弃未保存的观察？',content:'离开后不会生成观察点。已上传的照片仍保留在素材库。',confirmText:'放弃修改',cancelText:'继续编辑'});
        console.log('[开始] 放弃草稿确认');
        if(!answer.confirm){console.log('[分支] 继续编辑；[结束] 放弃草稿确认；[结束] 草稿修改检查；提前结束');return;}
        console.log('[分支] 放弃修改；[结束] 放弃草稿确认');
      }else{console.log('[分支] 空草稿直接返回');}
      console.log('[结束] 草稿修改检查');wx.navigateBack();return;
    }
    console.log('[分支] 已有观察点；[结束] 离开未保存观察点检查');
    if(dirty){const r=await modal({title:'保存观察记录？',content:'离开前可以保存刚才的修改。',confirmText:'保存',cancelText:'暂不保存'});if(r.confirm)await this.save();}wx.navigateBack();
  },
  async deleteNode(this:any){if(!node)return;const r=await modal({title:'删除观察点？',content:'观察点会移除，已有成图保留，素材库中的原始照片保留。'});if(!r.confirm)return;try{const local=localNode(nodeId);if(local&&!local.remote_id)throw new Error('离线观察点请先联网同步后删除');if(!node.layout_only)await request('/nodes/'+(local?.remote_id||nodeId),'DELETE');const active=getActiveTrack();if(active){active.nodes=active.nodes.filter(n=>n.id!==nodeId&&n.remote_id!==nodeId);localStore.Set('nature:gps:active',active);}dirty=false;wx.navigateBack();}catch(e){wx.showToast({title:errorMessage(e),icon:'none'});}}
};

function ReadObservationPosition(highAccuracy:boolean):Promise<any>{
  return new Promise((resolve,reject)=>(wx.getLocation as any)({type:'gcj02',enableHighAccuracy:highAccuracy,maximumAge:10000,timeout:highAccuracy?45000:15000,success:resolve,fail:reject}))
    .then(value=>value,error=>{console.log('浏览器位置读取失败：'+errorMessage(error));return null;});
}
