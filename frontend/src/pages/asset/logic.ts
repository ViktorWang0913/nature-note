import {DeleteMaterial} from '../../services/materials';
import * as localStore from './../../services/local-store';
import {request,operationId} from '../../services/api';
import {importAsset,currentProjectId} from '../../services/projects';
import {fail,go,preview,waitTask,query,confirm,decorateAsset} from '../../components/flows';
export default {
 data:{id:'',asset:null,loading:true,error:'',recognizing:false,recognition:null,recognitionError:'',showRecognition:false,speciesQ:'',speciesResults:[],selectedSpecies:'',selectedName:'',scientificName:'',confirmedBy:'user',selectedEvidence:null,observationText:'',saving:false,showCrop:false,showEditor:false,rotation:0,brightness:100,contrast:100,saturation:100,cropX:0,cropY:0,cropW:100,cropH:100,filter:'none',filterIndex:0,filters:['原色','暖色','冷色','黑白'],editLoading:false,editError:'',previewHeight:350,isCopy:true,observations:[]},
 _editCanvas:null as any,_editImage:null as any,_previewTimer:null as any,_autoRecognize:false,
 onLoad(o:any){this.setData({id:o.id});this._autoRecognize=o.recognize==='1';this.load();},
 onUnload(){if(this._previewTimer)clearTimeout(this._previewTimer);},
 async load(){this.setData({loading:true,error:''});try{const a:any=await request('/assets/'+this.data.id);const o:any=await request('/observations?'+query({asset_id:this.data.id,limit:100}));this.setData({asset:decorateAsset(a),observations:(o.items||[]).filter((x:any)=>x.asset_id===this.data.id)});if(this._autoRecognize){this._autoRecognize=false;this.recognize();}}catch(e){this.setData({error:(e as Error).message});}finally{this.setData({loading:false});}},
 preview(){preview((this.data.asset as any)?.url);},
 async favorite(){try{const a:any=this.data.asset;await request('/assets/'+a.id+'/favorite','PUT',{favorite:!a.favorite});this.setData({asset:{...a,favorite:!a.favorite}});}catch(e){fail(e);}},
 generate(){localStore.Set('aiAsset',this.data.asset);localStore.Set('galleryTab','ai');wx.switchTab({url:'/pages/gallery/index'});},
 async add(){try{const id=await importAsset(this.data.id);go('/pages/canvas/index?projectId='+id);}catch(e){fail(e);}},
 publish(){go('/pages/publish/index?assetId='+this.data.id);},
 AssetMenu(){const actions=[{title:'手动确认物种',run:()=>this.ManualConfirm(),visible:(this.data.asset as any)?.source==='photo'},{title:'删除素材',run:()=>this.remove(),visible:true}].filter(action=>action.visible);wx.showActionSheet({itemList:actions.map(action=>action.title),success:choice=>{console.log('[开始] 素材菜单');Promise.resolve(actions[choice.tapIndex].run()).then(()=>console.log('[结束] 素材菜单'),fail);}});},
 async recognize(){
  console.log('[开始] 识别输入检查');
  if(this.data.recognizing){console.log('[分支] 正在识别；[结束] 识别输入检查；提前返回');return;}
  const asset:any=this.data.asset;
  if(!asset?.editable||asset.source!=='photo'){console.log('[分支] 需要原始照片；[结束] 识别输入检查；提前返回');wx.showToast({title:'请用你拍摄的原始照片建立观察记录',icon:'none'});return;}
  console.log('[分支] 读取或提交此照片的识别；[结束] 识别输入检查');
  const assetId=this.data.id,key='nature:recognition:'+assetId;
  const pending=localStore.Get(key)||{operationId:operationId(),taskId:''};localStore.Set(key,pending);
  this.setData({recognizing:true,showRecognition:true,recognition:null,recognitionError:'',selectedSpecies:'',selectedName:''});
  const taskRequest=pending.taskId?request<any>('/tasks/'+pending.taskId):request<any>('/tasks','POST',{operation_id:pending.operationId,kind:'image_recognition',input:{asset_id:assetId}});
  await taskRequest.then(async task=>{
   pending.taskId=task.id;localStore.Set(key,pending);
   console.log('[开始] 已有识别状态');
   if(task.status==='failed'||task.status==='cancelled'){
    console.log('[分支] 显示原任务失败，本次不重新扣费；[结束] 已有识别状态；提前结束');localStore.Remove(key);
    throw new Error(task.error?.message||'上次识别未完成，可再次点击识别提交新任务');
   }
   console.log('[分支] 恢复原任务；[结束] 已有识别状态');
   const done=task.status==='succeeded'?task:await waitTask(task.id);this.setData({recognition:done.result});
  }).then(undefined,error=>this.setData({recognitionError:error.message})).finally(()=>this.setData({recognizing:false}));
 },
 closeRecognition(){this.setData({showRecognition:false});},noop(){},
 ChooseSpecies(e:any){
  const item = e.currentTarget.dataset;
  this.setData({selectedSpecies:item.id||'',selectedName:item.name||'',scientificName:item.scientific||'',confirmedBy:item.ai?'ai_suggestion':'user',selectedEvidence:item.ai?item:null});
 },
 SpeciesInput(e:any){this.setData({speciesQ:e.detail.value,selectedSpecies:'',selectedName:e.detail.value.trim(),scientificName:'',confirmedBy:'user',selectedEvidence:null});},
 ScientificInput(e:any){this.setData({scientificName:e.detail.value,selectedSpecies:'',confirmedBy:'user',selectedEvidence:null});},
 noteInput(e:any){this.setData({observationText:e.detail.value});},
 async searchSpecies(){try{const r:any=await request('/species?'+query({q:this.data.speciesQ}));this.setData({speciesResults:r.items});}catch(e){fail(e);}},
 async ConfirmSpecies(){
  console.log('[开始] 物种归档输入检查');
  if(!this.data.selectedName.trim()){
   console.log('[分支] 缺少确认名称');wx.showToast({title:'请输入或选择物种名称',icon:'none'});
   console.log('[结束] 物种归档输入检查；提前结束');return;
  }
  console.log('[分支] 用户已选择名称');console.log('[结束] 物种归档输入检查');
  const payload={asset_id:this.data.id,species_id:this.data.selectedSpecies||null,species_name:this.data.selectedName,
   scientific_name:this.data.scientificName,confirmed_by:this.data.confirmedBy,evidence:this.data.selectedEvidence||{},text:this.data.observationText};
  this.setData({saving:true});
  await request('/observations','POST',payload).then(()=>{
   this.setData({showRecognition:false});wx.showToast({title:'已归档到个人图鉴'});return this.load();
  },fail).finally(()=>this.setData({saving:false}));
 },
 async RemoveObservation(e:any){
  console.log('[开始] 移出图鉴确认');
  if(!await confirm('移出图鉴','原图和笔记保留，取消这张照片的物种归档。')){
   console.log('[分支] 用户取消');console.log('[结束] 移出图鉴确认；提前结束');return;
  }
  console.log('[分支] 用户确认');console.log('[结束] 移出图鉴确认');
  await request('/observations/'+e.currentTarget.dataset.id,'DELETE').then(()=>this.load(),fail);
 },
 ManualConfirm(){this.setData({showRecognition:true,recognition:null,recognitionError:'',selectedSpecies:'',selectedName:'',speciesQ:'',scientificName:'',selectedEvidence:null,confirmedBy:'user'});},
 async pending(){try{const existing:any=this.data.observations[0];if(existing)await request('/observations/'+existing.id,'PATCH',{species_id:null,text:this.data.observationText});else await request('/observations','POST',{asset_id:this.data.id,project_id:currentProjectId()||undefined,text:this.data.observationText});this.setData({showRecognition:false});wx.showToast({title:'已保存待确认记录'});this.load();}catch(e){fail(e);}},
 viewSpecies(e:any){go('/pages/species/index?id='+e.currentTarget.dataset.id);},
 edit(){this.setData({showEditor:true,editError:'',editLoading:true},()=>{this.initEditor();});},
 OpenCrop(){this.setData({showCrop:true});},
 CloseCrop(){this.setData({showCrop:false});},
 ApplyCrop(event:any){this.setData({...event.detail,showCrop:false});this.schedulePreview();},
 closeEditor(){this.setData({showEditor:false});this._editCanvas=null;this._editImage=null;},
 initEditor(){this.createSelectorQuery().select('#editCanvas').fields({node:true,size:true}).exec((result:any[])=>{try{if(!result[0]?.node)throw new Error('预览画布未就绪');const canvas=result[0].node;this._editCanvas=canvas;const image=canvas.createImage();image.onload=()=>{this._editImage=image;this.drawPreview();this.setData({editLoading:false});};image.onerror=()=>this.setData({editLoading:false,editError:'预览图片加载失败，可关闭后重新打开'});image.src=(this.data.asset as any).url;}catch(e){this.setData({editLoading:false,editError:(e as Error).message});}});},
 schedulePreview(){if(this._previewTimer)clearTimeout(this._previewTimer);this._previewTimer=setTimeout(()=>this.drawPreview(),100);},
 adjust(event:any){const field=event.currentTarget.dataset.field,value=Number(event.detail.value);this.setData({[field]:value});this.schedulePreview();},
 rotate(){this.setData({rotation:(this.data.rotation+90)%360});this.schedulePreview();},
 filter(e:any){const i=Number(e.detail.value);this.setData({filterIndex:i,filter:['none','warm','cool','grayscale'][i]});this.schedulePreview();},
 copy(e:any){this.setData({isCopy:e.detail.value});},
 reset(){this.setData({rotation:0,brightness:100,contrast:100,saturation:100,cropX:0,cropY:0,cropW:100,cropH:100,filter:'none',filterIndex:0});this.schedulePreview();},
 drawPreview(){const canvas=this._editCanvas,image=this._editImage;if(!canvas||!image)return;try{
 const sx=Math.round(image.width*this.data.cropX/100),sy=Math.round(image.height*this.data.cropY/100),sw=Math.max(1,Math.round(image.width*(this.data.cropX+this.data.cropW)/100)-sx),sh=Math.max(1,Math.round(image.height*(this.data.cropY+this.data.cropH)/100)-sy);
 const rotated=this.data.rotation%180!==0;const scale=Math.min(1,720/Math.max(sw,sh));const width=Math.max(1,Math.round((rotated?sh:sw)*scale)),height=Math.max(1,Math.round((rotated?sw:sh)*scale));canvas.width=width;canvas.height=height;this.setData({previewHeight:Math.round(height/width*694)});const ctx=canvas.getContext('2d');ctx.translate(width/2,height/2);ctx.rotate(this.data.rotation*Math.PI/180);ctx.drawImage(image,sx,sy,sw,sh,-sw*scale/2,-sh*scale/2,sw*scale,sh*scale);ctx.setTransform(1,0,0,1,0,0);
 const pixels=ctx.getImageData(0,0,width,height),d=pixels.data,b=this.data.brightness/100,c=this.data.contrast/100,s=this.data.saturation/100;
 for(let i=0;i<d.length;i+=4){let r=(d[i]*b-128)*c+128,g=(d[i+1]*b-128)*c+128,bl=(d[i+2]*b-128)*c+128;const gray=.299*r+.587*g+.114*bl;r=gray+(r-gray)*s;g=gray+(g-gray)*s;bl=gray+(bl-gray)*s;if(this.data.filter==='warm'){r*=1.08;bl*=.92;}else if(this.data.filter==='cool'){r*=.94;bl*=1.08;}else if(this.data.filter==='grayscale'){r=g=bl=gray;}d[i]=r;d[i+1]=g;d[i+2]=bl;}ctx.putImageData(pixels,0,0);
 }catch(e){this.setData({editError:(e as Error).message});}},
 async saveEdit(){if(this.data.saving)return;this.setData({saving:true});try{const a:any=await request('/assets/'+this.data.id+'/edit','POST',{rotation:this.data.rotation,brightness:this.data.brightness/100,contrast:this.data.contrast/100,saturation:this.data.saturation/100,crop:{x:this.data.cropX/100,y:this.data.cropY/100,width:this.data.cropW/100,height:this.data.cropH/100},filter:this.data.filter,save_as_copy:this.data.isCopy});this.setData({id:a.id,asset:decorateAsset(a),showEditor:false});wx.showToast({title:this.data.isCopy?'已另存副本':'已保存修改'});wx.redirectTo({url:'/pages/asset/index?id='+a.id});}catch(e){fail(e);}finally{this.setData({saving:false});}},
 async remove(){
  console.log('[开始] 详情删除互斥');
  if(this.data.saving){console.log('[分支] 正在处理；[结束] 详情删除互斥，提前结束');return;}
  console.log('[分支] 删除当前素材；[结束] 详情删除互斥');this.setData({saving:true});
  await DeleteMaterial(this.data.asset).then(deleted=>{console.log('[开始] 删除后返回');if(deleted){console.log('[分支] 返回素材库');localStore.Set('galleryTab','assets');wx.switchTab({url:'/pages/gallery/index'});}else{console.log('[分支] 保留详情');}console.log('[结束] 删除后返回');},fail).finally(()=>this.setData({saving:false}));
 }
};
