<template>
  <div class="app-shell">
    <NavBar
      :dark="dark"
      @new-chat="resetChat"
      @toggle-dark="toggleDark"
    />

    <div class="body">
      <!-- 左栏：历史会话（常驻） -->
      <HistorySidebar
        :history="history"
        :active="activeQuery"
        @select="send"
        @delete="removeHistory"
        @clear="clearHistory"
      />

      <!-- 中栏：对话 -->
      <main class="center">
        <section class="stage">
          <!-- 首屏 Hero（无对话时展示） -->
          <section v-if="messages.length === 0" class="hero">
            <h1 class="hero-title">用自然语言查询你的数据</h1>
            <p class="hero-sub">输入一个问题，Data Agent 自动理解、检索并生成答案</p>
            <div class="chips">
              <button v-for="s in suggestions" :key="s" class="chip" type="button" @click="send(s)">
                {{ s }}
              </button>
            </div>
            <div v-if="recentHistory.length" class="recent">
              <span class="recent-label">最近</span>
              <button v-for="h in recentHistory" :key="h.time" class="recent-item" type="button" @click="send(h.q)">
                {{ h.q }}
              </button>
            </div>
          </section>

          <!-- 对话流（搜索流程不再出现在这里，见右栏） -->
          <MessageList
            :messages="messages"
            @send="send"
            @retry="retry"
            @copy="copyResult"
            @export="exportResult"
          />
        </section>

        <!-- 悬浮输入栏（居中于中栏） -->
        <div class="composer-wrap">
          <form class="composer" @submit.prevent="send(question)">
            <input
              ref="inputEl"
              v-model="question"
              class="input-pill"
              type="text"
              :placeholder="loading ? '正在生成答案…' : '问我任何关于数据的问题，或输入 / 选择模板'"
              :disabled="loading"
              @keydown="onInputKeydown"
            />

            <!-- 斜杠命令菜单 -->
            <div v-if="showSlash" class="slash-menu">
              <div
                v-for="(t, i) in filteredSlash"
                :key="t.key"
                class="slash-item"
                :class="{ on: i === slashIndex }"
                @mousedown.prevent="applySlash(t)"
              >
                <b>{{ t.key }}</b>{{ t.label }}
                <small>{{ t.expand }}</small>
              </div>
              <div v-if="!filteredSlash.length" class="slash-item muted">没有匹配的模板</div>
            </div>

            <button v-if="loading" type="button" class="stop-btn" @click="stop">
              <span class="sq"></span>停止
            </button>
            <button v-else type="submit" class="send-btn" :disabled="!question.trim()" aria-label="发送">
              <svg width="18" height="18" viewBox="0 0 16 16">
                <path d="M3 8h9M8 4l4 4-4 4" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
          </form>
        </div>
      </main>

      <!-- 右栏：搜索流程（常驻） -->
      <StepsPanel :runs="runs" />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, computed, onMounted } from 'vue'
import NavBar from './components/NavBar.vue'
import MessageList from './components/MessageList.vue'
import HistorySidebar from './components/HistorySidebar.vue'
import StepsPanel from './components/StepsPanel.vue'

const API_URL = '/api/query'
const HISTORY_KEY = 'data-agent-history'
const DARK_KEY = 'data-agent-dark'

const question = ref('')
const loading = ref(false)
const messages = ref([])
const history = ref(loadHistory())
const inputEl = ref(null)
const activeQuery = ref('')
/* 右栏展示的查询流程，仅保留当前一次：{ q, steps:[{text,dur}], totalDur, done } */
const runs = ref([])

const suggestions = ['查询上个月总销售额', '哪个产品销量最高', '各区域销量对比']

const recentHistory = computed(() => history.value.slice(0, 3))

/* ── 深色模式 ── */
const dark = ref(false)
function toggleDark() {
  dark.value = !dark.value
  document.documentElement.classList.toggle('dark', dark.value)
  localStorage.setItem(DARK_KEY, dark.value ? '1' : '')
}
onMounted(() => {
  if (localStorage.getItem(DARK_KEY) === '1') toggleDark()
  window.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault()
      inputEl.value?.focus()
    }
  })
})

/* ── 历史管理 ── */
function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]')
  } catch {
    return []
  }
}
function pushHistory(q) {
  const list = loadHistory().filter((h) => h.q !== q)
  list.unshift({ q, time: Date.now() })
  history.value = list.slice(0, 30)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.value))
}
function removeHistory(time) {
  const list = loadHistory().filter((h) => h.time !== time)
  history.value = list
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.value))
}

function clearHistory() {
  history.value = []
  localStorage.removeItem(HISTORY_KEY)
}

function resetChat() {
  messages.value = []
  question.value = ''
  runs.value = []
}

/* ── 斜杠命令 ── */
const slashTemplates = [
  { key: '/月度', label: '按月汇总', expand: '按月汇总2025年销售额趋势' },
  { key: '/对比', label: '维度对比', expand: '各区域销量和销售额对比' },
  { key: '/排行', label: 'Top 排行', expand: '销量最高的前10个产品' },
]
const slashIndex = ref(0)
const showSlash = computed(() => question.value.startsWith('/'))
const filteredSlash = computed(() => {
  const q = question.value.slice(1).toLowerCase()
  return slashTemplates.filter((t) => (q ? t.key.slice(1).startsWith(q) || t.label.includes(q) : true))
})
function applySlash(t) {
  question.value = t.expand
  nextTick(() => inputEl.value?.focus())
}
function onInputKeydown(e) {
  if (showSlash.value && filteredSlash.value.length) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      slashIndex.value = (slashIndex.value + 1) % filteredSlash.value.length
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      slashIndex.value = (slashIndex.value - 1 + filteredSlash.value.length) % filteredSlash.value.length
      return
    }
    if (e.key === 'Tab' || (e.key === 'Enter' && filteredSlash.value[slashIndex.value])) {
      e.preventDefault()
      applySlash(filteredSlash.value[slashIndex.value])
    }
  }
}

/* ── 智能追问 ── */
function buildFollowups(q) {
  const base = q.replace(/\s*(是多少|是多少？|\?|\？)\s*$/, '')
  return [
    { label: '按月拆分看趋势', q: `${base}，按月拆分看趋势` },
    { label: '只看 2025 年 1 月', q: `2025年1月${base}` },
    { label: '对比销售额', q: `${base}，并对比销售额` },
  ]
}

/* ── 发送 / SSE ── */
let controller = null

function send(q, opts = {}) {
  const text = (q ?? question.value).trim()
  if (!text || loading.value) return

  loading.value = true
  question.value = ''
  slashIndex.value = 0
  activeQuery.value = text

  messages.value.push({ role: 'user', type: 'text', content: text })

  /* 本次查询的流程卡 → 右栏（不再进入聊天流）。
     必须 reactive()：普通对象直接改字段不经过代理，不会触发右栏重渲染。
     每次搜索整体重置：右栏只展示当前这一次的流程，从头开始 */
  const run = reactive({ q: text, steps: [], totalDur: 0, done: false })
  runs.value = [run]
  const steps = run.steps

  nextTick(scrollToBottom)

  if (!opts.silent) pushHistory(text)

  controller = new AbortController()
  const stageStart = performance.now()

  fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: text }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.body) throw new Error('服务器未返回数据流')
      const reader = response.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      const finalizeStep = () => {
        const now = performance.now()
        const last = steps.at(-1)
        if (last && last.dur === null) last.dur = +((now - last.start) / 1000).toFixed(1)
      }

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const events = buffer.split('\n\n')
        buffer = events.pop()

        for (const evt of events) {
          const line = evt.trim()
          if (!line.startsWith('data:')) continue
          let data
          try {
            data = JSON.parse(line.replace(/^data:\s*/, ''))
          } catch {
            continue
          }

          if (data.stage) {
            finalizeStep()
            steps.push({ text: data.stage, dur: null, start: performance.now() })
          } else if (data.error) {
            finalizeStep()
            messages.value.push({ role: 'assistant', type: 'error', content: data.error, retry: text })
          } else if (Array.isArray(data.result)) {
            finalizeStep()
            messages.value.push({
              role: 'assistant',
              type: 'table',
              columns: Object.keys(data.result[0] || {}),
              rows: data.result,
              view: 'table',
              followups: buildFollowups(text),
            })
          }
          nextTick(scrollToBottom)
        }
      }

      run.totalDur = +((performance.now() - stageStart) / 1000).toFixed(1)
      run.done = true
    })
    .catch((e) => {
      run.done = true
      if (e.name === 'AbortError') {
        messages.value.push({ role: 'assistant', type: 'error', content: '已停止生成。', retry: text })
      } else {
        messages.value.push({ role: 'assistant', type: 'error', content: e?.message || '请求失败', retry: text })
      }
    })
    .finally(() => {
      loading.value = false
      controller = null
      nextTick(scrollToBottom)
    })
}

function retry(text) {
  send(text)
}

function stop() {
  controller?.abort()
}

/* ── 复制 / 导出 ── */
function toCSV(m) {
  const cols = m.columns
  const head = cols.join(',')
  const body = m.rows
    .map((r) =>
      cols
        .map((c) => {
          const v = r[c]
          return v === null || v === undefined ? '' : String(v)
        })
        .join(',')
    )
    .join('\n')
  return head + '\n' + body
}
function copyResult(m) {
  navigator.clipboard?.writeText(toCSV(m))
}
function exportResult(m) {
  const blob = new Blob(['﻿' + toCSV(m)], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'data-agent-result.csv'
  a.click()
  URL.revokeObjectURL(url)
}

function scrollToBottom() {
  const el = document.querySelector('.messages')
  if (el) el.scrollTop = el.scrollHeight
}
</script>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  position: relative;
}
/* 三栏：历史 | 对话 | 流程 */
.body {
  flex: 1;
  min-height: 0;
  display: flex;
}
.center {
  flex: 1;
  min-width: 0;
  position: relative;
  display: flex;
}
.stage {
  flex: 1;
  overflow: hidden;
  position: relative;
}
.hero {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 0 24px 120px;
}
.hero-title {
  font-size: 44px;
  font-weight: 600;
  letter-spacing: -0.02em;
  margin: 0 0 14px;
  background: linear-gradient(180deg, #1d1d1f, #3a3a3c);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.hero-sub {
  font-size: 18px;
  color: var(--text-secondary);
  margin: 0 0 36px;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
  max-width: 640px;
}
.chip {
  border: 1px solid var(--border-strong);
  background: var(--surface);
  color: var(--text);
  padding: 10px 18px;
  border-radius: 999px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.chip:hover {
  border-color: var(--accent);
  color: var(--accent);
  transform: translateY(-1px);
  box-shadow: var(--shadow-soft);
}
.recent {
  margin-top: 28px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: center;
  max-width: 640px;
}
.recent-label {
  font-size: 13px;
  color: var(--text-tertiary);
}
.recent-item {
  border: none;
  background: transparent;
  color: var(--accent);
  font-size: 13px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 8px;
}
.recent-item:hover {
  background: var(--accent-soft);
}

/* 悬浮输入栏（相对中栏居中，不再横跨整屏） */
.composer-wrap {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 28px;
  display: flex;
  justify-content: center;
  padding: 0 16px;
  pointer-events: none;
  z-index: 20;
}
.composer {
  position: relative;
  pointer-events: auto;
  width: 100%;
  max-width: 720px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 10px 10px 16px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-input);
}
.input-pill {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 15px;
  color: var(--text);
}
.input-pill::placeholder {
  color: var(--text-tertiary);
}
.send-btn {
  width: 40px;
  height: 40px;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.15s ease;
}
.send-btn:hover:not(:disabled) {
  background: var(--accent-hover);
  transform: scale(1.05);
}
.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.stop-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: none;
  border-radius: 999px;
  padding: 8px 16px;
  background: var(--text);
  color: #fff;
  font-size: 13px;
  cursor: pointer;
  flex: 0 0 auto;
}
.stop-btn .sq {
  width: 9px;
  height: 9px;
  border-radius: 2px;
  background: #ff3b30;
}

/* 斜杠菜单 */
.slash-menu {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 8px;
  width: 300px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--shadow-soft);
  overflow: hidden;
  font-size: 13.5px;
}
.slash-item {
  padding: 10px 16px;
  cursor: pointer;
}
.slash-item b {
  color: var(--accent-deep);
  font-weight: 600;
  margin-right: 8px;
}
.slash-item small {
  display: block;
  color: var(--text-tertiary);
  margin: 2px 0 0 40px;
  font-size: 12px;
}
.slash-item.on,
.slash-item:hover {
  background: var(--accent-soft);
}
.slash-item.muted {
  color: var(--text-tertiary);
  cursor: default;
}

@media (max-width: 640px) {
  .hero-title {
    font-size: 32px;
  }
  .hero-sub {
    font-size: 16px;
  }
}
</style>
