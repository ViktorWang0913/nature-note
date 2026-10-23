import { errorMessage } from '../../services/api';
import {workspace} from '../../services/workspace';
import { chooseProject, currentProjectId, setCurrentProject } from '../../services/projects';
import { loadProject, flushQueue } from '../../services/sync';
import { getActiveTrack, subscribe, startTrack, pauseTrack, resumeTrack, endTrack, trackDuration, distance, syncTrack, LocalTrack } from '../../engine/tracker';
import { uid } from '../../engine/scene';
let unsubscribe:(()=>void)|null=null,timer:any=null,projectId='';
const modal=(o:any):Promise<any>=>new Promise(resolve=>wx.showModal({...o,success:resolve}));
export default {behaviors:[workspace],onResize(event:any){this.ResizeWindow(event);},data:{topInset:25,title:'自然观察',projectTitle:'自然观察',previousTrackTitle:'',hasPreviousTrack:false,otherTrack:false,status:'idle',statusLabel:'尚未开始',latitude:31.3,longitude:121.5,hasLocation:false,polyline:[] as any[],markers:[] as any[],duration:'00:00:00',distance:'0.00',nodeCount:0,busy:false,background:false,locationStatus:'等待定位',interrupted:false,syncError:''},
  async onLoad(this:any,options:any){this.setData({topInset:wx.getSystemInfoSync().statusBarHeight||25});projectId=options.project_id||options.projectId||currentProjectId();try{if(!projectId)projectId=await chooseProject();const p=await loadProject(projectId);this.setData({title:p.title,projectTitle:p.title});}catch(e){this.setData({syncError:errorMessage(e)});}unsubscribe=subscribe((track,error)=>{this.RefreshActiveTrack(track);console.log('[开始] 轨迹监听错误检查');if(error){console.log('[分支] 显示错误');this.setData({locationStatus:error});}else{console.log('[分支] 无错误');}console.log('[结束] 轨迹监听错误检查');});timer=setInterval(()=>this.RefreshClock(),1000);},
  RefreshActiveTrack(this:any,track:LocalTrack|null){
    const otherTrack=!!track&&track.project_id!==projectId&&track.status!=='ended';
    this.setData({otherTrack,hasPreviousTrack:!!track&&track.status!=='ended'&&(otherTrack||!!track.interrupted||track.status==='paused'),previousTrackTitle:track?.title||'上次观察'});
    console.log('[开始] 当前笔记轨迹显示');
    if(track?.project_id===projectId){console.log('[分支] 显示当前笔记轨迹');this.refresh(track);}
    else{console.log('[分支] 保持当前笔记并提供旧轨迹结束入口');this.setData({title:this.data.projectTitle,status:'idle',statusLabel:'尚未开始',duration:'00:00:00',distance:'0.00',nodeCount:0,polyline:[],markers:[],interrupted:false,background:false});}
    console.log('[结束] 当前笔记轨迹显示');
  },
  RefreshClock(this:any){
    const track=getActiveTrack();
    console.log('[开始] 记录计时更新');
    if(track?.project_id===projectId&&track.status==='recording'){
      console.log('[分支] 只更新时长，轨迹由定位事件更新');
      const seconds=Math.floor(trackDuration(track));
      this.setData({duration:[Math.floor(seconds/3600),Math.floor(seconds%3600/60),seconds%60].map(value=>String(value).padStart(2,'0')).join(':')});
    }else{console.log('[分支] 无正在进行的当前笔记记录');}
    console.log('[结束] 记录计时更新');
  },
  onShow(this:any){this.MeasureWindow();this.retrySync();},onUnload(){unsubscribe?.();unsubscribe=null;if(timer)clearInterval(timer);},
  refresh(this:any,t:LocalTrack){const groups:any[]=[];let segment=-1;for(const p of t.points){if(p.segment!==segment){groups.push({points:[],color:'#ff7b36',width:6,borderColor:'#ffffff',borderWidth:2});segment=p.segment;}groups[groups.length-1].points.push({latitude:p.latitude,longitude:p.longitude});}const seconds=Math.floor(trackDuration(t)),h=String(Math.floor(seconds/3600)).padStart(2,'0'),m=String(Math.floor(seconds%3600/60)).padStart(2,'0'),s=String(seconds%60).padStart(2,'0');const last=t.points[t.points.length-1];this.setData({title:t.title,status:t.status,statusLabel:t.status==='recording'?'正在记录':t.status==='paused'?'已暂停':'记录完成',duration:`${h}:${m}:${s}`,distance:(distance(t.points)/1000).toFixed(2),nodeCount:t.nodes.length,background:t.background,interrupted:!!t.interrupted,polyline:groups.filter(g=>g.points.length>1),markers:t.nodes.map((n,i)=>({id:i,latitude:n.latitude,longitude:n.longitude,width:25,height:25,callout:{content:String(i+1).padStart(2,'0')+(n.text?' '+n.text.slice(0,12):''),display:'ALWAYS',color:'#ffffff',bgColor:'#5ba774',borderRadius:16,padding:8,fontSize:12}})),...(last?{hasLocation:true,latitude:last.latitude,longitude:last.longitude,locationStatus:'GPS 精度约 '+Math.round(last.accuracy)+' 米'}:{locationStatus:'正在获取位置…'})});},
  async start(this:any){if(this.data.busy)return;this.setData({busy:true});try{if(!projectId)projectId=await chooseProject();await startTrack(projectId,this.data.title);}catch(e){const message=errorMessage(e);if(message.includes('auth')||message.includes('deny')){const r=await modal({title:'需要位置权限',content:'开启位置权限后，才能保存你的行动轨迹。',confirmText:'去设置'});if(r.confirm)wx.openSetting({});}else wx.showToast({title:message,icon:'none'});}finally{this.setData({busy:false});}},
  async toggle(this:any){this.setData({busy:true});try{if(this.data.status==='recording')await pauseTrack();else await resumeTrack();}catch(e){wx.showToast({title:errorMessage(e),icon:'none'});}finally{this.setData({busy:false});}},
  async end(this:any){
    console.log('[开始] 结束记录重复点击检查');
    if(this.data.busy){console.log('[分支] 等待当前操作；[结束] 结束记录重复点击检查；提前返回');return;}
    console.log('[分支] 打开一次确认框；[结束] 结束记录重复点击检查');this.setData({busy:true});
    const trackId=getActiveTrack()?.id;
    const answer=await modal({title:this.data.hasPreviousTrack?'结束之前轨迹？':'结束本次观察？',content:'已记录的轨迹和观察点会保留在原笔记中，结束后可以开始新的记录。'});
    console.log('[开始] 结束记录确认');
    if(!answer.confirm){console.log('[分支] 取消，继续记录；[结束] 结束记录确认；提前返回');this.setData({busy:false});return;}
    console.log('[分支] 保存并结束当前记录；[结束] 结束记录确认');
    console.log('[开始] 确认期间轨迹一致性');
    if(getActiveTrack()?.id!==trackId){console.log('[分支] 轨迹已切换；[结束] 确认期间轨迹一致性；提前结束');this.setData({busy:false});wx.showToast({title:'轨迹已切换，请重新操作',icon:'none'});return;}
    console.log('[分支] 仍为原轨迹；[结束] 确认期间轨迹一致性');
    await endTrack().then(()=>flushQueue()).then(()=>this.setData({syncError:''}),error=>this.setData({syncError:'记录已保存在本机：'+errorMessage(error)})).finally(()=>this.setData({busy:false}));
  },
  async design(this:any){
    await flushQueue();await syncTrack();await flushQueue();const track=getActiveTrack();
    console.log('[开始] 打开轨迹生成预览');
    if(track?.remote_id){console.log('[分支] 使用云端完整记录');setCurrentProject(track.project_id);wx.navigateTo({url:'/pages/canvas/index?projectId='+track.project_id+'&trackId='+track.remote_id});}
    else{console.log('[分支] 记录尚未同步');wx.showToast({title:'请先联网同步记录',icon:'none'});}
    console.log('[结束] 打开轨迹生成预览');
  },
  AddNode(this:any){
    console.log('[开始] 打开观察点草稿');
    if(this.data.busy){console.log('[分支] 等待当前操作；[结束] 打开观察点草稿；提前结束');return;}
    console.log('[分支] 先打开草稿；[结束] 打开观察点草稿');
    const track=getActiveTrack();
    console.log('[开始] 观察点所属轨迹检查');
    if(!track||track.project_id!==projectId||track.status==='ended'){
      console.log('[分支] 原轨迹不可用；[结束] 观察点所属轨迹检查；提前结束');
      wx.showToast({title:'请先开始当前笔记的轨迹记录',icon:'none'});return;
    }
    console.log('[分支] 编辑页后台定位，保存前不创建观察点；[结束] 观察点所属轨迹检查');
    const query=new URLSearchParams({id:uid('local-node'),draft:'1',project_id:track.project_id,track_id:track.id,time:new Date().toISOString()});
    wx.navigateTo({url:'/pages/node/index?'+query});
  },
  openNode(this:any,e:any){const node=getActiveTrack()?.nodes[e.detail.markerId];if(node)wx.navigateTo({url:'/pages/node/index?id='+(node.remote_id||node.id)+'&project_id='+node.project_id});},
  locate(){
    this.setData({locationStatus:'正在获取当前位置…'});
    wx.createMapContext('route-map').moveToLocation({
      success:(position:any)=>this.setData({hasLocation:true,latitude:position.latitude,longitude:position.longitude,locationStatus:'当前位置 · 精度约 '+Math.round(position.accuracy)+' 米'}),
      fail:()=>{this.setData({locationStatus:'定位失败，请检查浏览器位置权限'});wx.showToast({title:'暂时无法获取当前位置',icon:'none'});}
    });
  },
  async retrySync(this:any){try{await syncTrack();await flushQueue();this.setData({syncError:''});}catch(e){this.setData({syncError:'记录已保存在本机，等待联网同步。'});}},
  back(){wx.navigateBack({fail:()=>wx.switchTab({url:'/pages/home/index'})});}
};
