<script lang="ts">
import { defineComponent } from 'vue';
import definition from './logic';
import { UsePage } from '../../web/page';
export default defineComponent({setup(){return UsePage(definition);}});
</script>
<template>
  <div class="web-page atlas-screen">
    <nt-header page :brand="false" title="我的物种图鉴" description="把每一次发现，慢慢收进图鉴。">
        <svg class="atlas-illustration" viewBox="0 0 100 100" aria-hidden="true"><circle cx="54" cy="48" r="38"/><g><path d="M18 43q16-7 32 2 16-9 32-2v36q-16-7-32 2-16-9-32-2Zm32 2v36M26 54l15 3m-15 7 15 3m18-10 15-3m-15 13 15-3"/><path d="M48 37C32 36 31 22 33 15c15 1 22 12 15 22Zm3 2C49 24 64 18 75 21c-2 15-13 22-24 18Zm-3-2L39 24m12 15 13-10"/></g></svg>
    </nt-header>
    <main class="page tab-page atlas-page">
      <form class="search atlas-search" role="search" @submit.prevent="Dispatch('load',$event)">
        <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/></svg>
        <input :value="q" aria-label="搜索物种名称" @input="Dispatch('input',$event)" placeholder="搜索物种名称">
        <button type="submit">搜索</button>
      </form>
      <div class="chips sorting" aria-label="物种排序"><span class="sort-label">排序</span>
        <button v-for="option in [{id:'rarity',label:'稀有程度'},{id:'category',label:'物种分类'},{id:'count',label:'拍摄数量'}]" :key="option.id" class="chip" :class="{active:sort===option.id}" :aria-pressed="sort===option.id" :data-sort="option.id" @click="Dispatch('sort',$event)">{{option.label}}</button>
      </div>
      <div class="atlas-heading"><h2>{{resultQuery?'搜索结果':'收录物种'}}</h2><span v-if="!loading &amp;&amp; !error" class="collection-count">{{total===null?'已显示':'共'}} {{total===null?items.length:total}}{{total===null&amp;&amp;next?'+':''}} 种</span></div>
      <nt-state :loading="loading" :error="error" @retry="Dispatch('load',$event)" />
      <p v-if="!loading &amp;&amp; !error &amp;&amp; resultQuery &amp;&amp; !items.length" class="atlas-no-results">没有找到相关物种，换个名称试试。</p>
      <div class="species-grid">
        <button v-for="item in items" :key="item.id" class="card species-card" :data-id="item.id" @click="Dispatch('species',$event)">
          <img :src="item.image_url" :alt="item.name">
          <span class="card-info"><span class="h3 ellipsis">{{item.name}}</span><span class="muted small">{{item.photo_count||0}} 张</span></span>
        </button>
        <button class="card species-card add" @click="Dispatch('import',$event)">
          <span class="add-image"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg></span>
          <span class="card-info"><span class="h3">新增记录</span><span class="muted small">导入观察照片</span></span>
        </button>
      </div>
      <button v-if="next" class="section" @click="Dispatch('more',$event)">加载更多</button>
      <div v-if="items.length" class="empty small">点击物种，查看观察照片</div>
    </main>
  </div>
</template>
<style scoped>
.atlas-screen{--nn-content-width:1040px}.atlas-page{max-width:var(--nn-content-width);margin:auto;padding-top:0}.atlas-illustration{display:block;width:100%;height:100%}.atlas-illustration circle{fill:var(--nn-selected);opacity:.65}.atlas-illustration g{fill:none;stroke:#6e8565;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round}.atlas-search{background:var(--nn-panel);border-color:var(--nn-line)}.sorting{gap:8px;margin:16px 0 32px}.sort-label{margin-right:8px;color:var(--nn-muted);font-size:12px}.sorting .chip{min-height:44px;padding:10px 20px;border-radius:10px;font-size:13px}.atlas-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:20px}.atlas-heading h2{margin:0;font-size:18px;line-height:1.5}.collection-count{flex:none;color:var(--nn-muted);font-size:12px;font-variant-numeric:tabular-nums}.atlas-no-results{margin:0 0 20px;color:var(--nn-muted);font-size:13px}.species-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:20px}.species-card{display:flex;flex-direction:column;align-items:stretch;gap:0;min-width:0;padding:0;text-align:left;font-weight:400}.species-card>img,.add-image{width:100%;height:160px;object-fit:contain;background:var(--nn-soft)}.species-card .card-info{display:flex;flex-direction:column;gap:4px;min-width:0;width:100%;padding:16px}.species-card .h3{font-size:14px}.species-card .small{font-size:12px}.add-image{display:flex;align-items:center;justify-content:center;color:#7e9274}.add-image svg{width:32px;height:32px;fill:none;stroke:currentColor;stroke-width:1.5;stroke-linecap:round}
@media(max-width:600px){.sorting{gap:8px;margin-bottom:28px}.sort-label{display:none}.sorting .chip{flex:1;min-width:0;padding:10px 8px;font-size:12px}.species-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.species-card>img,.add-image{height:auto;aspect-ratio:4/3}.species-card .card-info{padding:12px}.atlas-heading h2{font-size:17px}}
</style>
