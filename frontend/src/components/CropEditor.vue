<script setup lang="ts">
import {computed,onBeforeUnmount,onMounted,ref} from 'vue';
import {ClampCrop,DragCrop,FitCrop,RotateCrop,fullCrop,type CropRect} from '../engine/crop';

// 参数设置：裁剪草稿只在应用时交回父页面。
const props=withDefaults(defineProps<{src:string;crop:CropRect;rotation?:number}>(),{rotation:0});
const emit=defineEmits<{apply:[crop:CropRect];cancel:[]}>();
const dialog=ref<HTMLDialogElement>(),host=ref<HTMLElement>(),stage=ref<HTMLElement>();
const draft=ref(RotateCrop(props.crop,props.rotation)),imageWidth=ref(0),imageHeight=ref(0),hostWidth=ref(0),hostHeight=ref(0);
const error=ref(''),preset=ref('自由'),active=ref(false);
const presets=[{label:'自由',ratio:0},{label:'原图',ratio:-1},{label:'1:1',ratio:1},{label:'4:3',ratio:4/3},{label:'3:4',ratio:3/4},{label:'16:9',ratio:16/9}];
const handles=[{key:'nw',label:'左上角',x:0,y:0},{key:'ne',label:'右上角',x:100,y:0},{key:'sw',label:'左下角',x:0,y:100},{key:'se',label:'右下角',x:100,y:100}];
const edges=[{key:'n',label:'上边',x:50,y:0},{key:'e',label:'右边',x:100,y:50},{key:'s',label:'下边',x:50,y:100},{key:'w',label:'左边',x:0,y:50}];
const swapped=props.rotation%180!==0;
const aspect=computed(()=>swapped?imageHeight.value/imageWidth.value:imageWidth.value/imageHeight.value);
const stageWidth=computed(()=>Math.max(0,Math.min(hostWidth.value-56,(hostHeight.value-56)*aspect.value))||0);
const stageHeight=computed(()=>stageWidth.value/aspect.value||0);
const ratio=computed(()=>{const chosen=presets.find(item=>item.label===preset.value)!;return chosen.ratio<0?1:chosen.ratio/aspect.value||0;});
const cropStyle=computed(()=>({left:draft.value.cropX+'%',top:draft.value.cropY+'%',width:draft.value.cropW+'%',height:draft.value.cropH+'%'}));
let observer:ResizeObserver,previousFocus:HTMLElement|null=null;
let gesture:{id:number;x:number;y:number;width:number;height:number;handle:string;crop:CropRect}|null=null;

// 主程序：原生模态窗口限制焦点；退出后恢复到触发按钮。
onMounted(()=>{
  previousFocus=document.activeElement as HTMLElement;dialog.value!.showModal();
  observer=new ResizeObserver(entries=>{hostWidth.value=entries[0].contentRect.width;hostHeight.value=entries[0].contentRect.height;EndGesture();});observer.observe(host.value!);
});
onBeforeUnmount(()=>{observer.disconnect();dialog.value?.close();previousFocus?.focus();});

// 自编函数
function ImageLoaded(event:Event){const image=event.target as HTMLImageElement;imageWidth.value=image.naturalWidth;imageHeight.value=image.naturalHeight;}
function ChoosePreset(label:string){EndGesture();preset.value=label;console.log('[开始] 裁剪比例切换');if(ratio.value){console.log('[分支] 适配固定比例');draft.value=FitCrop(draft.value,ratio.value);}else{console.log('[分支] 保持自由选区');}console.log('[结束] 裁剪比例切换');}
function Available(value:number){const normalized=value<0?1:value/aspect.value;return !value||(normalized>=.1&&normalized<=10);}
function ResetCrop(){EndGesture();preset.value='自由';draft.value={...fullCrop};}
function StartGesture(event:PointerEvent,handle:string){
  console.log('[开始] 裁剪指针检查');
  if(gesture||event.button!==0){console.log('[分支] 忽略额外指针；[结束] 裁剪指针检查，提前结束');return;}
  console.log('[分支] 锁定拖拽类型；[结束] 裁剪指针检查');
  const bounds=stage.value!.getBoundingClientRect();gesture={id:event.pointerId,x:event.clientX,y:event.clientY,width:bounds.width,height:bounds.height,handle,crop:{...draft.value}};
  stage.value!.setPointerCapture(event.pointerId);active.value=true;
}
function MoveGesture(event:PointerEvent){
  console.log('[开始] 裁剪拖动检查');
  if(!gesture||gesture.id!==event.pointerId){console.log('[分支] 忽略无关指针；[结束] 裁剪拖动检查，提前结束');return;}
  console.log('[分支] 更新草稿选区；[结束] 裁剪拖动检查');
  draft.value=DragCrop(gesture.crop,gesture.handle,(event.clientX-gesture.x)/gesture.width*100,(event.clientY-gesture.y)/gesture.height*100,ratio.value);
}
function EndGesture(event?:PointerEvent){
  console.log('[开始] 结束裁剪手势');
  if(gesture&&(!event||event.pointerId===gesture.id)){
    console.log('[分支] 释放当前拖拽');const pointerId=gesture.id;gesture=null;active.value=false;
    console.log('[开始] 指针捕获检查');if(stage.value?.hasPointerCapture(pointerId)){console.log('[分支] 释放捕获');stage.value.releasePointerCapture(pointerId);}else{console.log('[分支] 已释放');}console.log('[结束] 指针捕获检查');
  }else{console.log('[分支] 无当前拖拽');}console.log('[结束] 结束裁剪手势');
}
function KeyMove(event:KeyboardEvent,handle:string){
  const directions:Record<string,[number,number]>={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};
  console.log('[开始] 裁剪键盘检查');
  if(!directions[event.key]){console.log('[分支] 普通按键；[结束] 裁剪键盘检查，提前结束');return;}
  console.log('[分支] 按方向键调整选区；[结束] 裁剪键盘检查');event.preventDefault();const step=event.shiftKey?10:1,delta=directions[event.key];draft.value=DragCrop(draft.value,handle,delta[0]*step,delta[1]*step,ratio.value);
}
function ApplyCrop(){EndGesture();emit('apply',ClampCrop(RotateCrop(draft.value,-props.rotation)));}
</script>

<template>
  <Teleport to="body"><dialog ref="dialog" class="crop-editor" aria-labelledby="crop-title" @cancel.prevent="emit('cancel')">
    <header class="crop-header"><button autofocus @click="emit('cancel')">取消</button><strong id="crop-title">裁剪</strong><button class="crop-apply" :disabled="!imageWidth || !!error" @click="ApplyCrop">应用</button></header>
    <div ref="host" class="crop-workspace">
      <p v-if="error" role="alert">{{error}}</p><p v-else-if="!imageWidth" role="status">正在加载图片…</p>
      <div ref="stage" class="crop-stage" :class="{dragging:active}" :style="{width:stageWidth+'px',height:stageHeight+'px'}" @pointermove.prevent="MoveGesture" @pointerup="EndGesture" @pointercancel="EndGesture" @lostpointercapture="EndGesture">
        <img :src="src" alt="裁剪原图" draggable="false" @load="ImageLoaded" @error="error='图片加载失败，请关闭后重试'" :style="{width:(swapped?stageHeight:stageWidth)+'px',height:(swapped?stageWidth:stageHeight)+'px',transform:`translate(-50%,-50%) rotate(${rotation}deg)`}">
        <div v-if="imageWidth" class="crop-shade"><div :style="cropStyle"></div></div>
        <div v-if="imageWidth" class="crop-selection" :style="cropStyle" @pointerdown.stop.prevent="StartGesture($event,'move')">
          <button class="crop-move" aria-label="移动裁剪区域" @pointerdown.stop.prevent="StartGesture($event,'move')" @keydown="KeyMove($event,'move')"></button>
          <div v-show="active" class="crop-grid"></div>
          <button v-for="handle in handles" :key="handle.key" class="crop-handle" :data-handle="handle.key" :aria-label="'调整裁剪'+handle.label" :style="{left:handle.x+'%',top:handle.y+'%'}" @pointerdown.stop.prevent="StartGesture($event,handle.key)" @keydown="KeyMove($event,handle.key)"><span></span></button>
          <template v-if="!ratio"><button v-for="edge in edges" :key="edge.key" class="crop-handle crop-edge" :data-handle="edge.key" :aria-label="'调整裁剪'+edge.label" :style="{left:edge.x+'%',top:edge.y+'%'}" @pointerdown.stop.prevent="StartGesture($event,edge.key)" @keydown="KeyMove($event,edge.key)"><span></span></button></template>
        </div>
      </div>
    </div>
    <footer class="crop-footer"><div class="crop-presets" aria-label="裁剪比例"><button v-for="item in presets" :key="item.label" :aria-pressed="preset===item.label" :disabled="!imageWidth || !Available(item.ratio)" @click="ChoosePreset(item.label)">{{item.label}}</button></div><div class="crop-bottom"><span>拖动选区或边角裁剪</span><button @click="ResetCrop">重置裁剪</button></div></footer>
  </dialog></Teleport>
</template>

<style scoped>
.crop-editor{position:fixed;inset:0;margin:0;width:100vw;max-width:none;height:100vh;height:100dvh;max-height:none;padding:0;border:0;color:var(--nn-ink);background:var(--nn-panel);overflow:hidden}.crop-editor[open]{display:flex;flex-direction:column}.crop-editor::backdrop{background:#0008}.crop-header{display:flex;align-items:center;justify-content:space-between;flex:none;padding:8px 16px;padding-top:max(8px,env(safe-area-inset-top));border-bottom:1px solid var(--nn-line)}.crop-header strong{font-size:16px}.crop-editor button{font-size:14px;min-height:44px;border-radius:8px;padding:8px 14px}.crop-header button{min-width:64px}.crop-apply{background:var(--nn-accent);color:#fff}.crop-apply:disabled{opacity:.5}.crop-workspace{flex:1;min-height:0;position:relative;display:flex;align-items:center;justify-content:center;overflow:hidden;background:var(--nn-workspace)}.crop-workspace>p{position:absolute;text-align:center;padding:20px}.crop-stage{position:relative;touch-action:none;background:repeating-conic-gradient(#ddd 0% 25%,#fff 0% 50%) 0/16px 16px;flex:none}.crop-stage img{position:absolute;left:50%;top:50%;max-width:none;max-height:none;pointer-events:none;user-select:none}.crop-shade{position:absolute;inset:0;overflow:hidden;pointer-events:none}.crop-shade>div{position:absolute;box-shadow:0 0 0 2000px #0009}.crop-selection{position:absolute;border:1px solid #fff;box-sizing:border-box}.crop-editor .crop-move{z-index:2;clip-path:inset(20%);position:absolute;inset:0;width:100%;height:100%;min-height:0;min-width:0;padding:0;border:0;border-radius:0;background:transparent;cursor:move;touch-action:none}.crop-editor .crop-handle{position:absolute;transform:translate(-50%,-50%);width:44px;height:44px;min-width:44px;min-height:44px;padding:0;background:transparent;display:grid;place-items:center;touch-action:none;border:0;cursor:nwse-resize}.crop-handle span{width:12px;height:12px;background:white;border:2px solid var(--nn-accent);border-radius:3px;box-shadow:0 1px 4px #0005;pointer-events:none}.crop-editor .crop-edge{cursor:ew-resize}.crop-edge span{width:8px;height:8px}.crop-grid{position:absolute;inset:0;pointer-events:none;background:linear-gradient(to right,transparent 33.1%,#ffffff80 33.1%,#ffffff80 33.4%,transparent 33.4%,transparent 66.5%,#ffffff80 66.5%,#ffffff80 66.8%,transparent 66.8%),linear-gradient(to bottom,transparent 33.1%,#ffffff80 33.1%,#ffffff80 33.4%,transparent 33.4%,transparent 66.5%,#ffffff80 66.5%,#ffffff80 66.8%,transparent 66.8%)}.crop-footer{flex:none;padding:12px 16px max(8px,env(safe-area-inset-bottom));border-top:1px solid var(--nn-line)}.crop-presets{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:6px;max-width:640px;margin:auto}.crop-presets button{padding:8px 2px;background:var(--nn-soft);font-size:13px}.crop-presets button[aria-pressed=true]{background:var(--nn-accent);color:#fff}.crop-bottom{display:flex;align-items:center;justify-content:space-between;gap:8px;max-width:640px;margin:8px auto 0}.crop-bottom span{font-size:12px;color:var(--nn-muted)}.crop-bottom button{background:transparent;color:var(--nn-accent)}.crop-editor button:focus-visible{outline:2px solid var(--nn-focus);outline-offset:2px}@media(max-height:450px){.crop-footer{padding:4px 12px}.crop-bottom{margin:0}.crop-header{padding:4px 12px}}
</style>
