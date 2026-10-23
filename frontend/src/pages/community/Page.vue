<script lang="ts">
import {defineComponent} from 'vue';
import {UsePage} from '../../web/page';
import definition from './logic';
export default defineComponent({setup(){return UsePage(definition);}});
</script>
<template><div class="web-page"><nt-header/><main class="community-testing"><div class="testing-mark" aria-hidden="true">✳</div><h1>社区</h1><p role="status">测试中</p><a href="#/pages/home/index">返回首页</a></main></div></template>
<style scoped>.community-testing{min-height:65dvh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px;text-align:center;color:var(--nn-ink)}.testing-mark{font-size:52px;color:#6c8a72}.community-testing h1{font-size:24px;margin:20px 0 6px}.community-testing p{font-size:16px;color:var(--nn-muted)}.community-testing a{display:inline-flex;align-items:center;min-height:44px;color:var(--nn-accent);margin-top:20px}</style>
