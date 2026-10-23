<script lang="ts">
import { defineComponent } from 'vue';
import definition from './logic';
import { UsePage } from '../../web/page';
export default defineComponent({setup(){return UsePage(definition);}});
</script>
<template>
  <div class="web-page tutorial-page">
    <nt-header :brand="false" :back="true" title="三步完成自然笔记" />
    <main class="tutorial-content" aria-live="polite">
      <img v-if="step===0 && photos[0]?.url" :src="photos[0].url" alt="沿途拍摄观察照片" />
      <img v-else-if="step===1 && template" :src="template" alt="自然笔记模板示例" />
      <img v-else-if="step===2 && illustration" :src="illustration" alt="自然素材示例" />
      <div v-else class="tutorial-placeholder">{{ ['沿途记录发现','选择喜欢的风格','整理并保存笔记'][step] }}</div>
      <span class="step-number">{{ step+1 }} / 3</span>
      <h1>{{ titles[step] }}</h1>
      <p>{{ captions[step] }}</p>
      <p class="tutorial-detail">{{ ['开始记录后，在发现动植物的位置添加观察点，再上传照片并填写发现。结束记录会保留路线和观察点。','在同一本笔记中选择模板。模板只提供画面风格，路线、照片和地点来自你的观察。','先核对预览，再生成背景。你可以手动移动图片、编辑文字，保存并下载完成的笔记。'][step] }}</p>
    </main>
    <nav class="tutorial-actions" aria-label="教程步骤">
      <button v-if="step>0" @click="Dispatch('previous',$event)">上一步</button>
      <button v-if="step<2" class="primary" @click="Dispatch('next',$event)">下一步</button>
      <button v-else class="primary" @click="Dispatch('begin',$event)">开始一次自然观察</button>
    </nav>
  </div>
</template>
<style scoped>
.tutorial-page{min-height:100dvh;display:flex;flex-direction:column}.tutorial-content{flex:1;padding:20px;max-width:600px;width:100%;margin:auto;text-align:center}.tutorial-content img,.tutorial-placeholder{width:100%;height:min(32vh,260px);object-fit:contain;background:var(--nn-soft);border-radius:16px}.tutorial-placeholder{display:grid;place-items:center;color:var(--nn-accent)}.step-number{display:block;color:var(--nn-accent);font-size:18px;margin:20px 0 8px}.tutorial-content h1{font-size:24px;margin:8px 0}.tutorial-content p{font-size:15px;line-height:1.8}.tutorial-detail{color:var(--nn-muted);text-align:left}.tutorial-actions{position:sticky;bottom:0;display:flex;justify-content:center;gap:12px;padding:12px 20px calc(12px + env(safe-area-inset-bottom));background:var(--nn-panel);border-top:1px solid var(--nn-line)}.tutorial-actions button{min-height:44px;flex:1;max-width:360px}
</style>
