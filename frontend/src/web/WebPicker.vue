<script setup lang="ts">
import {nextTick,onBeforeUnmount,onMounted,ref,useId,watch} from 'vue';
defineOptions({inheritAttrs:false});
const props=withDefaults(defineProps<{range?:any[];rangeKey?:string;value?:any;disabled?:boolean}>(),{range:()=>[],value:0});
const emit=defineEmits(['change']);
const id=useId(),trigger=ref<HTMLButtonElement>(),menu=ref<HTMLElement>(),open=ref(false),active=ref(0);
const position=ref<Record<string,string>>({});
function Label(item:any){return String(props.rangeKey?item[props.rangeKey]:item);}
function Position(){
  const box=trigger.value!.getBoundingClientRect(),viewport=window.visualViewport;
  const left=viewport?.offsetLeft||0,top=viewport?.offsetTop||0,width=viewport?.width||innerWidth,height=viewport?.height||innerHeight;
  const below=top+height-box.bottom-14,above=box.top-top-14;
  const up=below<Math.min(288,props.range.length*44+14)&&above>below;
  const available=Math.max(0,up?above:below),menuHeight=Math.min(288,props.range.length*44+14,available);
  const menuWidth=Math.min(Math.max(box.width,176),width-24);
  position.value={left:Math.max(left+12,Math.min(box.left,left+width-menuWidth-12))+'px',top:(up?box.top-menuHeight-6:box.bottom+6)+'px',width:menuWidth+'px',maxHeight:menuHeight+'px'};
}
function BeforeToggle(event:ToggleEvent){open.value=event.newState==='open';if(open.value){active.value=Math.max(0,Math.min(Number(props.value)||0,props.range.length-1));Position();}}
async function Toggle(event:ToggleEvent){open.value=event.newState==='open';if(open.value){await nextTick();if(menu.value?.matches(':popover-open')){menu.value.focus();Reveal();}}}
function Reveal(){document.getElementById(id+'-'+active.value)?.scrollIntoView({block:'nearest'});}
function Close(focus=false){if(menu.value?.matches(':popover-open'))menu.value.hidePopover();if(focus)trigger.value?.focus();}
function Choose(index:number){emit('change',{detail:{value:index},dataset:trigger.value?.dataset});Close(true);}
function Keys(event:KeyboardEvent){
  const count=props.range.length;if(!count||props.disabled)return;
  if(!open.value){if(['ArrowDown','ArrowUp'].includes(event.key)){event.preventDefault();event.stopPropagation();menu.value?.showPopover();}return;}
  if(event.key==='Tab'){Close(true);return;}
  if(event.key==='Escape'){event.preventDefault();event.stopPropagation();Close(true);return;}
  if(!['ArrowDown','ArrowUp','Home','End','Enter',' '].includes(event.key))return;
  event.preventDefault();event.stopPropagation();
  if(event.key==='Enter'||event.key===' '){Choose(active.value);return;}
  active.value=event.key==='Home'?0:event.key==='End'?count-1:(active.value+(event.key==='ArrowDown'?1:-1)+count)%count;
  nextTick(Reveal);
}
function Dismiss(event:Event){if(event.target!==menu.value)Close();}
watch(()=>props.disabled,disabled=>{if(disabled)Close();});
watch(()=>props.range,()=>Close());
onMounted(()=>{window.addEventListener('resize',Dismiss);window.visualViewport?.addEventListener('resize',Dismiss);document.addEventListener('scroll',Dismiss,true);});
onBeforeUnmount(()=>{Close();window.removeEventListener('resize',Dismiss);window.visualViewport?.removeEventListener('resize',Dismiss);document.removeEventListener('scroll',Dismiss,true);});
</script>
<template>
  <button ref="trigger" v-bind="$attrs" type="button" class="web-picker" :class="{'is-disabled':disabled}" :disabled="disabled||!range.length" aria-haspopup="listbox" :aria-expanded="open" :aria-controls="id" :popovertarget="id" @keydown="Keys"><slot /></button>
  <div :id="id" ref="menu" class="web-picker-menu" popover="auto" role="listbox" :aria-label="$attrs['aria-label']||'选择'" :aria-activedescendant="id+'-'+active" tabindex="-1" :style="position" @beforetoggle="BeforeToggle" @toggle="Toggle" @keydown="Keys">
    <div v-for="(item,index) in range" :id="id+'-'+index" :key="index" role="option" :aria-selected="Number(value)===index" :class="{'is-active':active===index}" @pointermove="active=index" @click="Choose(index)">
      <span>{{Label(item)}}</span><svg v-if="Number(value)===index" viewBox="0 0 20 20" aria-hidden="true"><path d="m4 10 4 4 8-8"/></svg>
    </div>
  </div>
</template>
