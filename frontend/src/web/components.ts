import { defineComponent, h, ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue';
import { Navigate, WindowInfo, ShowError } from './platform';
export { default as PreviewImage } from './PreviewImage.vue';

export const NtHeader=defineComponent({props:{title:String,back:Boolean,brand:{type:Boolean,default:true},localBack:Boolean},emits:['back'],setup(props,{emit}){return()=>h('header',{class:'web-header'},[
  props.back?h('button',{class:'web-back','aria-label':'返回',onClick:()=>{console.log('[开始] 页头返回');if(props.localBack){console.log('[分支] 页面处理');emit('back');}else{console.log('[分支] 浏览器返回');wx.navigateBack();}console.log('[结束] 页头返回');}},'‹'):null,
  h('span',{class:props.brand?'web-brand':''},props.brand?'自然记':props.title)]);}});
export const NtBottom=defineComponent({props:{selected:{type:Number,default:0}},setup(props){const pages=['home','gallery','atlas','community'],labels=['首页','图库','图鉴','社区'],icons=['home','gallery','leaf','people'];return()=>h('nav',{class:'web-tabs'},pages.map((page,index)=>h('button',{class:{selected:props.selected===index},onClick:()=>Navigate('/pages/'+page+'/index')},[h('img',{src:'/assets/icons/'+icons[index]+(props.selected===index?'':'-muted')+'.svg',alt:''}),h('span',labels[index])])));}});
export const NtState=defineComponent({props:{loading:Boolean,error:String,empty:Boolean,message:{type:String,default:'暂无内容'}},emits:['retry'],setup(props,{emit}){return()=>props.loading?h('div',{class:'empty'},'正在加载…'):props.error?h('div',{class:'empty'},[h('p',props.error),h('button',{onClick:()=>emit('retry')},'重新加载')]):props.empty?h('div',{class:'empty'},props.message):null;}});
export const WebPicker=defineComponent({inheritAttrs:false,props:{range:{type:Array,default:()=>[]},rangeKey:String,value:{default:0},disabled:Boolean},emits:['change'],setup(props,{attrs,slots,emit}){return()=>h('div',{...attrs,class:['web-picker',attrs.class]},[slots.default?.(),h('select',{value:props.value,disabled:props.disabled,'aria-label':'选择',onChange:(event:any)=>emit('change',{detail:{value:Number(event.target.value)},dataset:attrs})},props.range.map((item:any,index)=>h('option',{value:index},props.rangeKey?item[props.rangeKey]:item)))]);}});
export const WebSlider=defineComponent({inheritAttrs:false,props:{min:{default:0},max:{default:100},step:{default:1},value:{default:0},disabled:Boolean},emits:['change'],setup(props,{attrs,emit}){return()=>h('input',{...attrs,...props,type:'range',onChange:(event:any)=>emit('change',{currentTarget:event.currentTarget,detail:{value:Number(event.target.value)}})});}});
export const WebSwitch=defineComponent({inheritAttrs:false,props:{checked:Boolean},emits:['change'],setup(props,{attrs,emit}){return()=>h('input',{...attrs,type:'checkbox',role:'switch',checked:props.checked,onChange:(event:any)=>emit('change',{detail:{value:event.target.checked},currentTarget:event.currentTarget})});}});
export const WebProgress=defineComponent({props:{percent:{default:0}},setup(props){return()=>h('progress',{max:100,value:props.percent});}});
export const WebScroll=defineComponent({props:{scrollTop:{default:0},scrollY:Boolean,lowerThreshold:{default:50}},emits:['lower'],setup(props,{slots,emit}){const element=ref<HTMLElement>();watch(()=>props.scrollTop,()=>nextTick(()=>{element.value?.scrollTo({top:Number(props.scrollTop)});}));return()=>h('div',{ref:element,style:{overflowY:'auto',minHeight:0,overscrollBehavior:'contain'},onScroll:(event:any)=>{const target=event.target;console.log('[开始] 滚动到底检查');if(target.scrollHeight-target.scrollTop-target.clientHeight<=Number(props.lowerThreshold)){console.log('[分支] 加载后续');emit('lower');}else{console.log('[分支] 继续浏览');}console.log('[结束] 滚动到底检查');}},slots.default?.());}});

let mapLoader:Promise<any>|undefined;
let mapKey='';
async function LoadMap(){
  const response=await fetch('/api/v1/web-config',{cache:'no-store'});
  const config=await response.json();
  console.log('[开始] 最新地图配置检查');
  if(!config.map_key){console.log('[分支] 缺少地图配置；[结束] 最新地图配置检查');throw new Error('地图尚未配置，定位记录仍可保存，请联系管理员');}
  console.log('[分支] 地图配置可用；[结束] 最新地图配置检查');
  console.log('[开始] 地图加载状态');
  if(mapLoader&&mapKey===config.map_key){console.log('[分支] 复用加载；[结束] 地图加载状态');return mapLoader;}
  console.log('[分支] 加载网页地图；[结束] 地图加载状态');
  mapKey=config.map_key;
  mapLoader=(async()=>{await new Promise<void>((resolve,reject)=>{const script=document.createElement('script');script.src='https://map.qq.com/api/gljs?v=1.exp&key='+encodeURIComponent(config.map_key);script.onload=()=>resolve();script.onerror=()=>{script.remove();reject(new Error('地图加载失败，请检查网络'));};document.head.append(script);});return (window as any).TMap;})().then(api=>api,failure=>{mapLoader=undefined;throw failure;});return mapLoader;
}
export const WebMap=defineComponent({props:{id:String,latitude:Number,longitude:Number,located:Boolean,polyline:Array,markers:Array,scale:{default:17}},emits:['marker'],setup(props,{emit}){
  const element=ref<HTMLElement>(),error=ref('');let map:any,lines:any,markers:any,currentMarker:any,mapApi:any;
  let centeredOnPosition=false,disposed=false;
  let pendingPosition:{latitude:number;longitude:number}|undefined;
  function Update(){console.log('[开始] 地图就绪检查');if(!map){console.log('[分支] 尚未加载；[结束] 地图就绪检查');return;}console.log('[分支] 更新线和点；[结束] 地图就绪检查');
    lines.setGeometries((props.polyline||[]).map((line:any,index)=>({id:String(index),styleId:'route',paths:line.points.map((point:any)=>new mapApi.LatLng(point.latitude,point.longitude))})));
    markers.setGeometries((props.markers||[]).map((marker:any)=>({id:String(marker.id),styleId:'point',position:new mapApi.LatLng(marker.latitude,marker.longitude),properties:{title:marker.callout?.content||String(marker.id+1)}})));
  }
  function Locate(event:Event){
    const position=(event as CustomEvent).detail;
    console.log('[开始] 地图定位目标检查');
    if(position?.mapId!==props.id||!Number.isFinite(position?.latitude)||!Number.isFinite(position?.longitude)){
      console.log('[分支] 非当前地图或坐标无效；[结束] 地图定位目标检查；提前结束');return;
    }
    console.log('[分支] 使用本次定位坐标；[结束] 地图定位目标检查');
    pendingPosition=position;centeredOnPosition=true;
    map?.setCenter(new mapApi.LatLng(position.latitude,position.longitude));
    UpdatePosition();
  }
  function UpdatePosition(){
    const position=pendingPosition||props;
    console.log('[开始] 当前位置标记');
    if(currentMarker&&(pendingPosition||props.located)){
      console.log('[分支] 显示独立蓝点');
      currentMarker.setGeometries([{id:'current-location',styleId:'current',position:new mapApi.LatLng(position.latitude,position.longitude)}]);
    }else{console.log('[分支] 等待有效定位');}
    console.log('[结束] 当前位置标记');
  }
  function CenterFirstPosition(){
    console.log('[开始] 首次定位居中检查');
    if(map&&props.located&&!centeredOnPosition){
      console.log('[分支] 首次有效定位，显示当前位置');
      map.setCenter(new mapApi.LatLng(props.latitude,props.longitude));centeredOnPosition=true;
    }else{console.log('[分支] 保留用户当前地图视野');}
    console.log('[结束] 首次定位居中检查');
  }
  onMounted(()=>{LoadMap().then(api=>{
    console.log('[开始] 地图页面生命周期检查');
    if(disposed){console.log('[分支] 页面已离开；[结束] 地图页面生命周期检查；提前结束');return;}
    console.log('[分支] 初始化当前地图；[结束] 地图页面生命周期检查');
    mapApi=api;const center=pendingPosition||props;
    map=new api.Map(element.value,{center:new api.LatLng(center.latitude,center.longitude),zoom:Number(props.scale),pitch:0});
    centeredOnPosition=Boolean(pendingPosition||props.located);
    lines=new api.MultiPolyline({map,styles:{route:new api.PolylineStyle({color:'#ff7b36',width:6})}});markers=new api.MultiMarker({map,styles:{point:new api.MarkerStyle({width:25,height:35})}});markers.on('click',(event:any)=>emit('marker',{detail:{markerId:Number(event.geometry.id)}}));
    currentMarker=new api.MultiMarker({map,styles:{current:new api.MarkerStyle({width:28,height:28,anchor:{x:14,y:14},src:'/assets/icons/current-location.svg'})}});
    Update();UpdatePosition();
  },failure=>{error.value=failure.message;});window.addEventListener('nature-map-locate',Locate);});
  watch(()=>[props.polyline,props.markers],Update,{deep:true});
  watch(()=>[props.latitude,props.longitude,props.located],()=>{pendingPosition=undefined;CenterFirstPosition();UpdatePosition();});
  onBeforeUnmount(()=>{disposed=true;map?.destroy();window.removeEventListener('nature-map-locate',Locate);});
  return()=>h('div',{class:'web-map'},[h('div',{ref:element,style:{width:'100%',height:'100%'}}),error.value?h('p',{class:'web-map-error',role:'status'},error.value):null]);
}});
