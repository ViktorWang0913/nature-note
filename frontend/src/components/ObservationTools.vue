<script setup lang="ts">
import {ref} from 'vue';
import FloatingPanel from './FloatingPanel.vue';
import Chat from '../pages/chat/Page.vue';
import Gallery from '../pages/gallery/Page.vue';
const active=ref(''),chatOpened=ref(false),imageOpened=ref(false),input=ref<any>(null);
const emit=defineEmits(['open']);
function Open(kind:string){active.value=kind;if(kind==='chat')chatOpened.value=true;else if(kind==='image')imageOpened.value=true;emit('open',!!kind);}
function Toggle(kind:string){Open(active.value===kind?'':kind);}
function Creation(payload:any){input.value=payload;Open('image');}
</script>
<template>
  <div class="observation-tools" aria-label="观察助手"><button aria-label="问问自然记" :aria-expanded="active==='chat'" @click="Toggle('chat')"><img src="/assets/icons/chat.svg" alt=""></button><button aria-label="图片创作" :aria-expanded="active==='image'" @click="Toggle('image')"><img src="/assets/icons/pen.svg" alt=""></button></div>
  <FloatingPanel trigger-selector=".observation-tools" :open="!!active" :title="active==='chat'?'问问自然记':'图片创作'" @close="Open('')"><Chat v-if="chatOpened" v-show="active==='chat'" embedded :active="active==='chat'" @creation="Creation" /><Gallery v-if="imageOpened" v-show="active==='image'" embedded creation-only initial-tab="ai" :active="active==='image'" :creation-input="input" @close="Open('')" /></FloatingPanel>
</template>
<style scoped>
.observation-tools{position:absolute;right:16px;bottom:76px;z-index:2;display:flex;flex-direction:column;gap:12px}.observation-tools button{width:46px;height:46px;min-height:46px;padding:12px;background:var(--nn-floating);backdrop-filter:blur(14px) saturate(115%);-webkit-backdrop-filter:blur(14px) saturate(115%);border:1px solid var(--nn-floating-border);border-radius:50%;box-shadow:0 3px 12px #20392b18}.observation-tools button[aria-expanded=true]{background:var(--nn-selected);border-color:var(--nn-focus)}.observation-tools img{width:22px;height:22px}
</style>
