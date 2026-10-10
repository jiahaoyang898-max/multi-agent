<template>
  <header class="nav">
    <div class="nav-left">
      <div class="logo">
        <svg width="16" height="16" viewBox="0 0 14 14">
          <path
            d="M2 9l3-5 2 3 2-4 3 6"
            fill="none"
            stroke="#fff"
            stroke-width="1.5"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </div>
      <span class="brand">Data Agent</span>
    </div>

    <div class="nav-right">
      <div class="status" :title="connected ? '数据源已连接' : '数据源未连接'">
        <span v-for="s in sources" :key="s" class="status-item">
          <span class="dot" :class="{ on: connected }"></span>{{ s }}
        </span>
      </div>

      <span class="kbd-hint num">⌘K</span>

      <button class="icon-btn" title="深色模式" aria-label="深色模式" @click="$emit('toggle-dark')">
        <svg v-if="!dark" width="17" height="17" viewBox="0 0 16 16">
          <path d="M13 8.5A5.5 5.5 0 1 1 7.5 3a4.5 4.5 0 0 0 5.5 5.5Z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" />
        </svg>
        <svg v-else width="17" height="17" viewBox="0 0 16 16">
          <circle cx="8" cy="8" r="3.2" fill="none" stroke="currentColor" stroke-width="1.3" />
          <path d="M8 1.5v1.6M8 12.9v1.6M14.5 8h-1.6M3.1 8H1.5M12.6 3.4l-1.1 1.1M4.5 11.5l-1.1 1.1M12.6 12.6l-1.1-1.1M4.5 4.5 3.4 3.4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" />
        </svg>
      </button>
      <button class="icon-btn" title="新建对话" aria-label="新建对话" @click="$emit('new-chat')">
        <svg width="17" height="17" viewBox="0 0 16 16">
          <path d="M3 8h10M8 3v10" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
        </svg>
      </button>
      <button class="icon-btn" title="历史会话" aria-label="历史会话" @click="$emit('open-history')">
        <svg width="17" height="17" viewBox="0 0 16 16">
          <circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.3" />
          <path d="M8 4.6V8l2.4 1.4" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
    </div>
  </header>
</template>

<script setup>
// 注：connected 为视觉健康度指示，默认 true（环境就绪时）。
// 若以后后端提供 /health 等健康检查端点，可在此处轮询真实状态。
// dark 状态由父组件（App）统一控制并响应 toggle-dark 事件。
defineProps({ dark: { type: Boolean, default: false } })
defineEmits(['open-history', 'new-chat', 'toggle-dark'])
const sources = ['MySQL', 'ES', 'Qdrant', 'Embed']
const connected = true
</script>

<style scoped>
.nav {
  position: sticky;
  top: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 22px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border-bottom: 1px solid var(--border);
}
.nav-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.logo {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--accent), #7aa3cf);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(94, 139, 192, 0.4);
}
.brand {
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -0.01em;
}
.nav-right {
  display: flex;
  align-items: center;
  gap: 14px;
}
.status {
  display: flex;
  gap: 14px;
}
.status-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12.5px;
  color: var(--text-secondary);
}
.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #d2d2d7;
}
.dot.on {
  background: #34c759;
  box-shadow: 0 0 0 3px rgba(52, 199, 89, 0.18);
}
.kbd-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  padding: 1px 7px;
  background: var(--surface);
}
.icon-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}
.icon-btn:hover {
  background: rgba(0, 0, 0, 0.05);
  color: var(--accent);
}

@media (max-width: 640px) {
  .status,
  .kbd-hint {
    display: none;
  }
}
</style>
