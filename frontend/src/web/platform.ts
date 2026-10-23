import { nextTick, reactive } from 'vue';
import { ReadValue, WriteValue, RemoveValue, StorageInfo, ReadFile, WriteFile, CurrentAccount } from './storage';
import { ReadBlob, MediaUrl } from './media';
import coordtransform from 'coordtransform';

export const ui=reactive({toast:'',dialog:null as any,preview:'',tabHidden:false});
let toastTimer:ReturnType<typeof setTimeout>;
let locationWatch:number|undefined;
let locationEpoch=0;
let locationListener:((position:any)=>void)|undefined;
let leaveMessage='';
let rawSequence=0;
const recordingId=crypto.randomUUID();
export let currentPage:any=null;

export function SetCurrentPage(page:any){currentPage=page;}
export function ShouldBlockNavigation(){return Boolean(leaveMessage&&currentPage?.data?.dirty);}
export function ShowError(error:any){ShowToast({title:error?.message||String(error)});}
export function ShowToast(options:any){ui.toast=options.title;clearTimeout(toastTimer);toastTimer=setTimeout(()=>{ui.toast='';},options.duration||3000);}
export function Complete(options:any,result:any){options.success?.(result);options.complete?.(result);return result;}
export function Fail(options:any,error:any){options.fail?.(error);options.complete?.(error);console.log('[开始] 错误显示');if(!options.fail){console.log('[分支] 显示错误');ShowError(error);}else{console.log('[分支] 交给调用者');}console.log('[结束] 错误显示');}
export function ResolveDialog(result:any){const dialog=ui.dialog;ui.dialog=null;dialog?.resolve(result);}
export function Ask(options:any):Promise<any>{return new Promise(resolve=>{ui.dialog={...options,resolve};});}
export function WindowInfo(){return {windowWidth:innerWidth,windowHeight:visualViewport?.height||innerHeight,screenWidth:screen.width,screenHeight:screen.height,statusBarHeight:0,pixelRatio:devicePixelRatio,safeArea:{top:0,bottom:innerHeight,left:0,right:innerWidth}};}
export function Canvas(canvas:HTMLCanvasElement){(canvas as any).createImage=()=>new Image();return canvas;}
export function SelectorQuery(){
  let selector='';const query={select(value:string){selector=value;return query;},fields(){return query;},boundingClientRect(){return query;},exec(callback:any){nextTick(()=>{const node=document.querySelector(selector);const box=node?.getBoundingClientRect();console.log('[开始] 画布节点适配');if(node instanceof HTMLCanvasElement){console.log('[分支] Canvas2D');Canvas(node);}else{console.log('[分支] 普通元素');}console.log('[结束] 画布节点适配');callback([{node,width:box?.width||0,height:box?.height||0,top:box?.top||0,left:box?.left||0}]);});}};return query;
}
export function Navigate(url:string,replace=false){
  console.log('[开始] 页面离开检查');
  if(leaveMessage&&currentPage?.data?.dirty){console.log('[分支] 保存后再离开');currentPage.pendingNavigation=()=>Navigate(url,replace);currentPage.Leave();console.log('[结束] 页面离开检查；提前等待用户选择');return;}
  console.log('[分支] 可以离开；[结束] 页面离开检查');
  console.log('[开始] 导航类型');if(replace){console.log('[分支] 替换页面');location.replace('#'+url);}else{console.log('[分支] 新页面');location.hash=url;}console.log('[结束] 导航类型');
}
export function StopLocation(){locationEpoch++;console.log('[开始] 定位监听停止');if(locationWatch!==undefined){console.log('[分支] 清除监听');navigator.geolocation.clearWatch(locationWatch);locationWatch=undefined;}else{console.log('[分支] 没有监听');}console.log('[结束] 定位监听停止');}
export function Position(position:GeolocationPosition){
  const accountId=CurrentAccount(),raw={latitude:position.coords.latitude,longitude:position.coords.longitude,accuracy:position.coords.accuracy,timestamp:position.timestamp,coordinate_system:'wgs84'};
  WriteValue(`nature:account:${accountId}:nature:gps:raw:${recordingId}:${rawSequence++}`,raw);
  const converted=coordtransform.wgs84togcj02(raw.longitude,raw.latitude);
  return {...raw,longitude:converted[0],latitude:converted[1],coordinate_system:'gcj02'};
}

// 主程序：只映射本项目实际使用的宿主接口，页面业务继续使用原有数据契约。
export function InstallPlatform(){
  const platform:any={
    getStorageSync:ReadValue,setStorageSync:WriteValue,removeStorageSync:RemoveValue,getStorageInfoSync:StorageInfo,
    getWindowInfo:WindowInfo,getSystemInfoSync:WindowInfo,nextTick,
    getMenuButtonBoundingClientRect:()=>({top:0,left:innerWidth,width:0,height:0}),
    showToast:ShowToast,
    showModal(options:any){Ask({kind:'modal',...options}).then(result=>Complete(options,result));},
    showActionSheet(options:any){Ask({kind:'actions',...options}).then(result=>{console.log('[开始] 选项确认');if(result.confirm){console.log('[分支] 选中');Complete(options,{tapIndex:result.tapIndex});}else{console.log('[分支] 取消');options.fail?.({errMsg:'cancel'});}console.log('[结束] 选项确认');});},
    previewImage(options:any){ui.preview=options.current||options.urls[0];Complete(options,{});},
    navigateTo(options:any){Navigate(options.url);},redirectTo(options:any){Navigate(options.url,true);},switchTab(options:any){Navigate(options.url);},reLaunch(options:any){Navigate(options.url,true);},
    navigateBack(){console.log('[开始] 浏览器返回');if(history.state?.naturePage){console.log('[分支] 返回上一页');history.back();}else{console.log('[分支] 回到首页');Navigate('/pages/home/index',true);}console.log('[结束] 浏览器返回');},
    createSelectorQuery:SelectorQuery,
    createOffscreenCanvas(options:any){const canvas=Canvas(document.createElement('canvas'));canvas.width=options.width;canvas.height=options.height;return canvas;},
    canvasToTempFilePath(options:any){options.canvas.toBlob((blob:Blob)=>{console.log('[开始] 画布导出');if(blob){console.log('[分支] PNG完成');Complete(options,{tempFilePath:URL.createObjectURL(blob)});}else{console.log('[分支] 导出失败');Fail(options,new Error('导出失败'));}console.log('[结束] 画布导出');},'image/png');},
    chooseMedia(options:any){const input=document.createElement('input');input.type='file';input.accept='image/jpeg,image/png,image/webp';console.log('[开始] 拍照来源');if(options.sourceType?.length===1&&options.sourceType[0]==='camera'){console.log('[分支] 使用相机');input.capture='environment';}else{console.log('[分支] 选择照片');}console.log('[结束] 拍照来源');input.onchange=()=>{const file=input.files?.[0];console.log('[开始] 照片选择结果');if(file){console.log('[分支] 已选择');Complete(options,{tempFiles:[{tempFilePath:URL.createObjectURL(file),size:file.size}]});}else{console.log('[分支] 取消');options.fail?.({errMsg:'cancel'});}console.log('[结束] 照片选择结果');};input.oncancel=()=>options.fail?.({errMsg:'cancel'});input.click();},
    saveImageToPhotosAlbum(options:any){ReadBlob(options.filePath).then(async blob=>{const file=new File([blob],'自然记.png',{type:'image/png'});console.log('[开始] 图片保存方式');if(matchMedia('(pointer: coarse)').matches&&navigator.canShare?.({files:[file]})){console.log('[分支] 系统保存或分享');await navigator.share({files:[file]});}else{console.log('[分支] 浏览器下载');const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='自然记.png';link.click();}console.log('[结束] 图片保存方式');}).then(()=>Complete(options,{}),error=>Fail(options,error));},
    downloadFile(options:any){ReadBlob(options.url).then(blob=>Complete(options,{statusCode:200,tempFilePath:URL.createObjectURL(blob)}),error=>Fail(options,error));},
    env:{USER_DATA_PATH:'webfile:'},
    getFileSystemManager(){return {copyFile(options:any){const accountId=CurrentAccount();ReadBlob(options.srcPath).then(async blob=>{console.log('[开始] 文件账号检查');if(accountId!==CurrentAccount()){console.log('[分支] 已切换；[结束] 文件账号检查');throw new Error('账号已切换');}console.log('[分支] 当前账号；[结束] 文件账号检查');await WriteFile(options.destPath,blob);}).then(()=>Complete(options,{}),error=>Fail(options,error));}};},
    getNetworkType(options:any){Complete(options,{networkType:navigator.onLine?'wifi':'none'});},
    onNetworkStatusChange(listener:any){window.addEventListener('online',()=>listener({isConnected:true}));window.addEventListener('offline',()=>listener({isConnected:false}));},
    authorize(options:any){console.log('[开始] 定位能力');if(!window.isSecureContext||!navigator.geolocation){console.log('[分支] 不可定位');Fail(options,new Error('请通过 HTTPS 打开网页并允许定位'));}else{console.log('[分支] 由浏览器在定位时请求授权');Complete(options,{});}console.log('[结束] 定位能力');},
    startLocationUpdateBackground(options:any){options.fail?.(new Error('网页仅支持前台定位'));},
    startLocationUpdate(options:any){StopLocation();const accountId=CurrentAccount(),watchEpoch=locationEpoch;locationWatch=navigator.geolocation.watchPosition(position=>{console.log('[开始] 定位回调账号边界');if(accountId!==CurrentAccount()||watchEpoch!==locationEpoch){console.log('[分支] 旧回调已丢弃；[结束] 定位回调账号边界');return;}console.log('[分支] 当前账号和片段；[结束] 定位回调账号边界');locationListener?.(Position(position));},error=>{console.log('[开始] 定位错误回调检查');if(accountId!==CurrentAccount()||watchEpoch!==locationEpoch){console.log('[分支] 旧错误已丢弃；[结束] 定位错误回调检查');return;}console.log('[分支] 当前定位失败；[结束] 定位错误回调检查');ShowError(new Error(error.message));window.dispatchEvent(new Event('nature-location-interrupted'));},{enableHighAccuracy:true,timeout:20000,maximumAge:0});Complete(options,{});},
    stopLocationUpdate(options:any={}){StopLocation();Complete(options,{});},
    onLocationChange(listener:any){locationListener=listener;},
    getLocation(options:any){const accountId=CurrentAccount(),watchEpoch=locationEpoch;navigator.geolocation.getCurrentPosition(position=>{console.log('[开始] 单次定位账号边界');if(accountId!==CurrentAccount()||watchEpoch!==locationEpoch){console.log('[分支] 旧定位拒绝；[结束] 单次定位账号边界');Fail(options,new Error('定位已中断，请重新定位'));return;}console.log('[分支] 当前定位；[结束] 单次定位账号边界');Complete(options,Position(position));},error=>Fail(options,new Error(error.message)),{enableHighAccuracy:options.enableHighAccuracy??true,timeout:options.timeout??20000,maximumAge:options.maximumAge??0});},
    createMapContext(mapId:string){return {moveToLocation(options:any={}){
      platform.getLocation({success:(position:any)=>{
        window.dispatchEvent(new CustomEvent('nature-map-locate',{detail:{mapId,...position}}));
        Complete(options,position);
      },fail:(error:any)=>Fail(options,error)});
    }};},
    openSetting(){ShowToast({title:'请在浏览器的网站设置中允许位置访问'});},
    hideKeyboard(){(document.activeElement as HTMLElement)?.blur?.();},
    enableAlertBeforeUnload(options:any){leaveMessage=options.message;},disableAlertBeforeUnload(){leaveMessage='';},
    login(options:any){Fail(options,new Error('请使用管理员分配的账号登录'));}
  };
  Object.assign(globalThis,{wx:platform,Behavior:(definition:any)=>definition,getCurrentPages:()=>history.state?.naturePage?[{},currentPage]:[currentPage],getApp:()=>({globalData:{networkConnected:navigator.onLine}})});
  window.addEventListener('beforeunload',event=>{console.log('[开始] 浏览器关闭检查');if(leaveMessage){console.log('[分支] 提示未保存');event.preventDefault();event.returnValue=leaveMessage;}else{console.log('[分支] 无未保存设计');}console.log('[结束] 浏览器关闭检查');});
  window.addEventListener('nature-storage-error',(event:any)=>ShowToast({title:'本机保存失败：'+event.detail}));
}
