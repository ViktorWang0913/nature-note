<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';

const props=defineProps<{src?:string;eager?:boolean;alt?:string}>();
const element=ref<HTMLImageElement>();
const visible=ref(Boolean(props.eager));
let observer:IntersectionObserver|undefined;

onMounted(()=>{
  console.log('[开始] 预览图加载范围');
  if(props.eager){console.log('[分支] 首屏主图立即加载');}
  else{
    console.log('[分支] 进入视口附近再加载');
    observer=new IntersectionObserver(entries=>{
      console.log('[开始] 预览图可见检查');
      if(entries.some(entry=>entry.isIntersecting)){
        console.log('[分支] 可以开始下载');visible.value=true;observer?.disconnect();
      }else{console.log('[分支] 屏幕外图片继续等待');}
      console.log('[结束] 预览图可见检查');
    },{rootMargin:'160px'});
    observer.observe(element.value!);
  }
  console.log('[结束] 预览图加载范围');
});
onBeforeUnmount(()=>observer?.disconnect());
</script>

<template><img ref="element" :src="visible ? src : undefined" :alt="alt || ''" decoding="async" :fetchpriority="eager ? 'high' : 'auto'" /></template>
