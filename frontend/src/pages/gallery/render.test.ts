import { expect, test, vi } from 'vitest';
import { createSSRApp, defineComponent, h } from 'vue';
import { renderToString } from 'vue/server-renderer';

const fixture = vi.hoisted(() => ({ data: {} as Record<string, any> }));
vi.mock('../../services/workspace', () => ({ workspace: {} }));
vi.mock('../../web/storage', () => ({}));
vi.mock('../../web/page', async ImportOriginal => {
  const original = await ImportOriginal<typeof import('../../web/page')>();
  return { ...original, UsePage: () => ({ ...fixture.data, Safe: original.Safe, Style: original.Style, Dispatch: vi.fn() }) };
});
import page from './Page.vue';
import definition from './logic';
import PreviewImage from '../../web/PreviewImage.vue';

// 主程序：直接渲染生产 Vue 模板，避免只测任务接口而漏掉结果卡片。
test.each(['history', 'completed', 'paired'])('成功图片显示在聊天区：%s', async mode => {
  const task = { id: 'render-task', status: 'succeeded', result: { image_url: '/render-result.png' } };
  fixture.data = { ...structuredClone(definition.data), tab: 'ai', viewportHeight: 844,
    result: task.result, task, resultHasMessage: mode !== 'completed',
    messages: mode === 'paired' ? [{ role: 'user', text: '画一片叶子', task }, { role: 'assistant', text: '图片生成完成', task }] : mode === 'history' ? [{ role: 'user', text: '画一片叶子', task }] : [] };
  const app = createSSRApp(page);
  app.component('PreviewImage', PreviewImage);
  app.component('WebScroll', defineComponent({ setup: (_, { slots }) => () => h('div', slots.default?.()) }));
  app.component('WebPicker', defineComponent({ setup: (_, { slots }) => () => h('div', slots.default?.()) }));
  app.component('nt-header', defineComponent({ setup: () => () => h('header') }));
  app.component('nt-state', defineComponent({ setup: () => () => h('div') }));
  const html = await renderToString(app);
  expect(html).toContain('src="/render-result.png"');
  expect(html).toContain('保存素材');
  expect(html).toContain('继续修改');
  expect(html).not.toMatch(/<template(?:\s|>)/);
  expect(html.match(/class="image-result"/g)).toHaveLength(1);
});
