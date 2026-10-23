<script setup lang="ts">
defineProps<{ sessions: any[]; sessionId: string; busy: boolean; creation?: boolean }>();
defineEmits(['new', 'open', 'history']);
</script>

<template>
  <aside class="conversation-rail" aria-label="会话导航">
    <button class="rail-new" :disabled="busy" @click="$emit('new')"><span>＋</span>{{ creation ? '新创作' : '新对话' }}</button>
    <div class="rail-heading">{{ creation ? '最近创作' : '最近对话' }}</div>
    <nav class="rail-sessions">
      <button v-for="session in sessions" :key="session.id" :class="['rail-session', { active: session.id === sessionId }]"
        :aria-current="session.id === sessionId ? 'page' : undefined" :disabled="busy" :data-id="session.id" @click="$emit('open', $event)">
        <span>{{ session.title }}</span><span class="rail-arrow">↗</span>
      </button>
      <p v-if="!sessions.length" class="rail-empty">发送第一条消息后，<br>会话会保存在这里。</p>
    </nav>
    <button class="rail-manage" :disabled="busy" @click="$emit('history')">查看与管理历史 <span>↗</span></button>
    <div class="rail-footer">自然记<span>把发现留下来</span></div>
  </aside>
</template>
