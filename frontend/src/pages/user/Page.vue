<script lang="ts">
import { defineComponent } from "vue";
import definition from "./logic";
import { UsePage } from "../../web/page";
export default defineComponent({setup(){return UsePage(definition);}});
</script>
<template><div class="web-page"><nt-header :brand="Safe(() =&gt; (false))" :back="true" title="观察者主页"></nt-header><div class="page"><nt-state :loading="Safe(() =&gt; (loading))" :error="Safe(() =&gt; (error))" @retry="Dispatch('load', $event)"></nt-state><template v-if="Safe(() =&gt; (user))"><div class="surface row"><img v-if="Safe(() =&gt; (user.avatar_url))" class="avatar" :src="Safe(() =&gt; (user.avatar_url))"></img><div v-else class="avatar avatar-fallback">♧</div><div class="grow"><div class="h2">{{ Safe(() => (user.nickname)) }}</div><div class="small muted">{{ Safe(() => (user.title||'自然观察者')) }}</div></div><button v-if="Safe(() =&gt; (user.id!==me))" :class="&quot;mini round &quot; + String(Safe(() =&gt; (user.following?&#x27;&#x27;:&#x27;primary&#x27;)) ?? &quot;&quot;)" @click="Dispatch('follow', $event)">{{ Safe(() => (user.following?'已关注':'＋ 关注')) }}</button><button v-else class="mini" @click="Dispatch('profile', $event)">编辑资料</button></div><div class="row section"><span class="h2">公开笔记</span><span class="muted small">{{ Safe(() => (posts.length)) }} 篇</span></div><div class="grid2 section"><template v-for="(item, index) in Safe(() => (posts))" :key="index"><div class="card" @click="Dispatch('open', $event)" :data-id="Safe(() =&gt; (item.id))"><img class="cover" :src="Safe(() =&gt; (item.cover))" mode="aspectFill"></img><div class="card-info h3">{{ Safe(() => (item.title)) }}</div></div></template></div><div v-if="Safe(() =&gt; (!posts.length))" class="empty">暂时没有公开分享</div></template></div>
</div></template>
<style scoped>
.cover{height:160px}.avatar{width:50px;height:50px}

</style>
