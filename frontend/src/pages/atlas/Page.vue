<script lang="ts">
import { defineComponent } from "vue";
import definition from "./logic";
import { UsePage } from "../../web/page";
export default defineComponent({setup(){return UsePage(definition);}});
</script>
<template><div class="web-page"><nt-header ></nt-header><div class="page tab-page">
<div class="row profile-row"><img v-if="Safe(() =&gt; (user.avatar_url))" :src="Safe(() =&gt; (user.avatar_url))" class="avatar" @click="Dispatch('profile', $event)"></img><div v-else class="avatar avatar-fallback" @click="Dispatch('profile', $event)">♧</div><div class="grow" @click="Dispatch('profile', $event)"><div class="h2">{{ Safe(() => (user.nickname||'自然观察者')) }}</div><div class="muted">{{ Safe(() => (user.title||'记录每一次发现')) }}</div></div><button class="outline round mini" @click="Dispatch('achievements', $event)">♜ 成就 ›</button></div>
<div class="search section"><span class="search-icon">⌕</span><input :value="Safe(() =&gt; (q))" @input="Dispatch('input', $event)" @keyup.enter="Dispatch('load', $event)" confirm-type="search" placeholder="搜索物种名称"></input><span @click="Dispatch('load', $event)">搜索</span></div>
<div class="chips sorting"><span :class="&quot;chip &quot; + String(Safe(() =&gt; (sort===&#x27;rarity&#x27;?&#x27;active&#x27;:&#x27;&#x27;)) ?? &quot;&quot;)" data-sort="rarity" @click="Dispatch('sort', $event)">稀有程度 ﹀</span><span :class="&quot;chip &quot; + String(Safe(() =&gt; (sort===&#x27;category&#x27;?&#x27;active&#x27;:&#x27;&#x27;)) ?? &quot;&quot;)" data-sort="category" @click="Dispatch('sort', $event)">物种分类 ﹀</span><span :class="&quot;chip &quot; + String(Safe(() =&gt; (sort===&#x27;count&#x27;?&#x27;active&#x27;:&#x27;&#x27;)) ?? &quot;&quot;)" data-sort="count" @click="Dispatch('sort', $event)">拍摄数量 ﹀</span></div>
<div class="row section"><span class="h2">我的物种图鉴</span><span class="muted small">已记录 {{ Safe(() => (recorded)) }} 种</span></div><nt-state :loading="Safe(() =&gt; (loading))" :error="Safe(() =&gt; (error))" @retry="Dispatch('load', $event)"></nt-state>
<div class="grid3 section"><template v-for="(item, index) in Safe(() => (items))" :key="index"><div class="card species-card" :data-id="Safe(() =&gt; (item.id))" @click="Dispatch('species', $event)"><img :src="Safe(() =&gt; (item.image_url))" mode="aspectFit"></img><div class="card-info"><div class="h3">{{ Safe(() => (item.name)) }}</div><div class="muted small">{{ Safe(() => (item.photo_count||0)) }} 张</div></div></div></template><div class="card species-card add" @click="Dispatch('import', $event)"><div class="add-image">＋</div><div class="card-info"><div class="h3">新增记录</div><div class="muted small">导入观察照片</div></div></div></div>
<button v-if="Safe(() =&gt; (next))" class="section" @click="Dispatch('more', $event)">加载更多</button><div class="empty small">点击物种，查看观察照片</div></div>
</div></template>
<style scoped>
.profile-row{padding:7.5px 0 6px}.profile-row .avatar{width:52px;height:52px}.profile-row .muted{font-size:12.5px;margin-top:2.5px}.sorting{gap:6px}.sorting .chip{flex:1;text-align:center;padding:9px 3px;font-size:12.5px;border-radius:12px}.species-card img,.add-image{width:100%;height:83.5px;background:var(--nn-soft)}.species-card .card-info{padding:7.5px 7.5px 9.5px}.species-card .h3{font-size:12.5px;margin-bottom:2.5px}.species-card .small{font-size:11px}.add-image{display:flex;align-items:center;justify-content:center;color:#c3c8d1;font-size:40px}

</style>
