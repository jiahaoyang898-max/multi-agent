<template>
  <aside class="rail">
    <div class="rail-head">
      <span class="rail-title">历史会话</span>
      <button v-if="history.length" class="clear-btn" type="button" @click="$emit('clear')">清空</button>
    </div>

    <div class="rail-search" v-if="history.length">
      <input v-model="search" class="search-input" type="text" placeholder="搜索历史问题…" />
    </div>

    <div v-if="!filtered.length" class="rail-empty">
      {{ search ? '没有匹配的历史记录' : '还没有历史记录' }}
    </div>
    <ul class="history-list" v-else>
      <li v-for="h in filtered" :key="h.time" class="history-item" :class="{ on: h.q === active }" @click="$emit('select', h.q)">
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
  history: { type: Array, default: () => [] },
  active: { type: String, default: '' },
})
defineEmits(['select', 'delete', 'clear'])

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
.rail {
  width: 264px;
  flex: 0 0 264px;
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--surface-2);
  border-right: 1px solid var(--border);
}
.rail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px 10px;
}
.rail-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  letter-spacing: 0.01em;
}
.clear-btn {
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  font-size: 12px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 6px;
}
.clear-btn:hover {
  color: #ff3b30;
  background: rgba(255, 59, 48, 0.08);
}
.rail-search {
  padding: 0 14px 8px;
}
.search-input {
  width: 100%;
  border: 1px solid var(--border-strong);
  background: var(--surface);
  border-radius: 10px;
  padding: 8px 12px;
  font-size: 13px;
  color: var(--text);
  outline: none;
}
.search-input:focus {
  border-color: var(--accent);
}
.rail-empty {
  padding: 36px 18px;
  text-align: center;
  color: var(--text-tertiary);
  font-size: 13px;
}
.history-list {
  list-style: none;
  margin: 0;
  padding: 4px 10px 14px;
  overflow-y: auto;
  flex: 1;
}
.history-item {
  padding: 9px 10px;
  border-radius: 10px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: background 0.15s ease;
}
.history-item:hover {
  background: var(--accent-soft);
}
.history-item.on {
  background: var(--accent-soft);
}
.history-item.on .h-q {
  color: var(--accent-deep);
  font-weight: 500;
}
.h-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.h-q {
  font-size: 13.5px;
  color: var(--text);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.h-time {
  font-size: 11.5px;
  color: var(--text-tertiary);
}
.h-del {
  flex: 0 0 auto;
  width: 26px;
  height: 26px;
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
@media (max-width: 920px) {
  .rail {
    display: none;
  }
}
</style>
