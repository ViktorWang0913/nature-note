import { reactive, toRefs, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { SelectorQuery, SetCurrentPage, ShowError, WindowInfo, ui } from './platform';

export function Safe(Read:()=>any){try{return Read();}catch(error){console.log('[开始] 页面字段读取');if(error instanceof TypeError){console.log('[分支] 数据尚未加载；[结束] 页面字段读取');return undefined;}console.log('[分支] 非字段错误；[结束] 页面字段读取');throw error;}}
export function Style(value:any){return String(value??'').replace(/(-?\d+(?:\.\d+)?)rpx/g,(_match,number)=>Number(number)/2+'px');}
export function UsePage(definition:any){
  const behaviors=definition.behaviors||[],baseData=Object.assign({},...behaviors.map((behavior:any)=>behavior.data||{}),definition.data);
  const data=reactive(structuredClone(baseData));
  const pointerTouches=new Map<number,{x:number;y:number;identifier:number}>();
  const context:any={...definition,...Object.assign({},...behaviors.map((behavior:any)=>behavior.methods||{})),data,unloaded:false,
    setData(patch:any,callback?:()=>void){
      console.log('[开始] 页面状态更新');
      const entries=Object.entries(patch);
      if(entries.every(([key])=>!/[.\[]/.test(key))){console.log('[分支] 批量更新顶层字段');Object.assign(data,patch);}
      else{console.log('[分支] 更新嵌套字段');console.log('[开始] 嵌套字段循环');entries.forEach(([path,value],index)=>{console.log(`[开始] 字段 ${index+1}/${entries.length}`);const parts=path.replace(/\[(\d+)\]/g,'.$1').split('.'),last=parts.pop()!;const parent=parts.reduce((parent:any,key)=>parent[key],data);parent[last]=value;console.log(`[结束] 字段 ${index+1}/${entries.length}`);});console.log('[结束] 嵌套字段循环');}
      console.log('[结束] 页面状态更新');nextTick(callback);
    },
    createSelectorQuery:SelectorQuery,getTabBar:()=>({setData(patch:any){ui.tabHidden=patch.hidden??ui.tabHidden;}}),triggerEvent(){}};
  console.log('[开始] 页面方法绑定');Object.keys(context).forEach((key,index,keys)=>{console.log(`[开始] 方法 ${index+1}/${keys.length}`);console.log('[开始] 方法类型');if(typeof context[key]==='function'){console.log('[分支] 绑定页面');context[key]=context[key].bind(context);}else{console.log('[分支] 页面状态');}console.log('[结束] 方法类型');console.log(`[结束] 方法 ${index+1}/${keys.length}`);});console.log('[结束] 页面方法绑定');
  function Dispatch(name:string,event:any){
    const target=event?.currentTarget||event?.target,box=target?.getBoundingClientRect?.()||{left:0,top:0};
    const dataset={...target?.dataset,...event?.dataset};console.log('[开始] 事件数据转换');Object.keys(dataset).forEach((key,index,keys)=>{console.log(`[开始] 事件字段 ${index+1}/${keys.length}`);console.log('[开始] 布尔值检查');if(dataset[key]==='true'||dataset[key]==='false'){console.log('[分支] 布尔值');dataset[key]=dataset[key]==='true';}else{console.log('[分支] 普通值');}console.log('[结束] 布尔值检查');console.log(`[结束] 事件字段 ${index+1}/${keys.length}`);});console.log('[结束] 事件数据转换');
    const detail=typeof event?.detail==='object'?event.detail:{value:target?.type==='checkbox'?target.checked:target?.value};
    console.log('[开始] 画布指针输入检查');
    if(event?.type?.startsWith('pointer')){
      console.log('[分支] 统一鼠标、触控笔和触屏输入');
      console.log('[开始] 指针生命周期');
      if(event.type==='pointerup'||event.type==='pointercancel'){
        console.log('[分支] 释放指针');pointerTouches.delete(event.pointerId);
      }else if(event.type==='pointerdown'||pointerTouches.has(event.pointerId)){
        console.log('[分支] 记录按下或拖动位置');
        target.setPointerCapture(event.pointerId);pointerTouches.set(event.pointerId,{x:event.clientX-box.left,y:event.clientY-box.top,identifier:event.pointerId});
      }else{console.log('[分支] 忽略未按下的悬停');}
      console.log('[结束] 指针生命周期');
    }else{console.log('[分支] 普通页面事件');}
    console.log('[结束] 画布指针输入检查');
    const touches=event?.type?.startsWith('pointer')?[...pointerTouches.values()]:Array.from(event?.touches||[]).map((touch:any)=>({x:touch.clientX-box.left,y:touch.clientY-box.top,identifier:touch.identifier}));
    const normalized={...event,nativeEvent:event,currentTarget:{dataset},target:{dataset},detail,touches};
    const result=context[name]?.(normalized);result?.then?.(undefined,ShowError);
  }
  function Resize(){context.onResize?.({size:WindowInfo()});}
  onMounted(async()=>{SetCurrentPage(context);ui.tabHidden=false;const query=location.hash.split('?')[1]||'';await context.onLoad?.(Object.fromEntries(new URLSearchParams(query)));await nextTick();context.onShow?.();context.onReady?.();window.addEventListener('resize',Resize);visualViewport?.addEventListener('resize',Resize);});
  onBeforeUnmount(()=>{context.onHide?.();context.onUnload?.();context.unloaded=true;window.removeEventListener('resize',Resize);visualViewport?.removeEventListener('resize',Resize);});
  return {...toRefs(data),pageData:data,Dispatch,Safe,Style};
}
