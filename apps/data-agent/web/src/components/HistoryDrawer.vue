<template>
  <div class="drawer-mask" v-if="open" @click="$emit('close')"></div>
  <aside class="drawer" :class="{ open }">
    <div class="drawer-head">
      <span class="drawer-title">历史会话</span>
      <button class="drawer-close" type="button" @click="$emit('close')">关闭</button>
    </div>

    <div class="drawer-search" v-if="history.length">
      <input v-model="search" class="search-input" type="text" placeholder="搜索历史问题…" />
    </div>

    <div v-if="!filtered.length" class="drawer-empty">
      {{ search ? '没有匹配的历史记录' : '还没有历史记录' }}
    </div>
    <ul class="history-list" v-else>
      <li v-for="h in filtered" :key="h.time" class="history-item" @click="$emit('select', h.q)">
        <div class="h-main">
          <span class="h-q">{{ h.q }}</span>
          <span class="h-time">{{ formatTime(h.time) }}</span>
        </div>
        <button
          class="h-del"
          type="button"
          title="删除"
          aria-label="删除"
          @click.stop="$emit('delete', h.time)"
        >
          <svg width="14" height="14" viewBox="0 0 14 14">
            <path d="M3 3.5l8 7M11 3.5l-8 7" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
          </svg>
        </button>
      </li>
    </ul>
  </aside>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  open: Boolean,
  history: { type: Array, default: () => [] },
})
defineEmits(['close', 'select', 'delete'])

const search = ref('')

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return props.history
  return props.history.filter((h) => h.q.toLowerCase().includes(q))
})

function formatTime(t) {
  const d = new Date(t)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
</script>

<style scoped>
.drawer-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.18);
  z-index: 40;
  animation: fade 0.2s ease;
}
.drawer {
  position: fixed;
  top: 0;
  right: 0;
  height: 100%;
  width: 340px;
  max-width: 84vw;
  background: var(--surface);
  box-shadow: -10px 0 40px rgba(0, 0, 0, 0.12);
  z-index: 41;
  transform: translateX(100%);
  transition: transform 0.28s cubic-bezier(0.22, 0.61, 0.36, 1);
  display: flex;
  flex-direction: column;
}
.drawer.open {
  transform: translateX(0);
}
.drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px;
  border-bottom: 1px solid var(--border);
}
.drawer-title {
  font-size: 16px;
  font-weight: 600;
}
.drawer-close {
  border: none;
  background: transparent;
  color: var(--accent);
  font-size: 14px;
  cursor: pointer;
}
.drawer-search {
  padding: 12px 16px 4px;
}
.search-input {
  width: 100%;
  border: 1px solid var(--border-strong);
  background: var(--surface-2);
  border-radius: 10px;
  padding: 9px 12px;
  font-size: 13.5px;
  color: var(--text);
  outline: none;
}
.search-input:focus {
  border-color: var(--accent);
}
.drawer-empty {
  padding: 40px 20px;
  text-align: center;
  color: var(--text-tertiary);
  font-size: 14px;
}
.history-list {
  list-style: none;
  margin: 0;
  padding: 8px 12px;
  overflow-y: auto;
  flex: 1;
}
.history-item {
  padding: 10px 12px;
  border-radius: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: background 0.15s ease;
}
.history-item:hover {
  background: var(--accent-soft);
}
.h-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.h-q {
  font-size: 14px;
  color: var(--text);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.h-time {
  font-size: 12px;
  color: var(--text-tertiary);
}
.h-del {
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.15s ease, color 0.15s ease, background 0.15s ease;
}
.history-item:hover .h-del {
  opacity: 1;
}
.h-del:hover {
  color: #ff3b30;
  background: rgba(255, 59, 48, 0.1);
}
@keyframes fade {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
</style>
