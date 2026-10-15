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
      <span
        v-if="authUnknown"
        class="auth-warn"
        :title="authWarnTitle"
      >无法确认登录态</span>

      <div class="status" :title="connected ? '数据源已连接' : '数据源未连接'">
        <span v-for="s in sources" :key="s" class="status-item">
          <span class="dot" :class="{ on: connected }"></span>{{ s }}
        </span>
      </div>

      <span class="kbd-hint num">⌘K</span>

      <button
        class="back-btn"
        type="button"
        title="返回智枢工作台（不清登录状态）"
        @click="backToWorkbench"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 11 12 4l8 7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
          <path d="M6 10v9h12v-9" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        返回工作台
      </button>

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
    </div>
  </header>
</template>

<script setup>
// 注：connected 为视觉健康度指示，默认 true（环境就绪时）。
// 若以后后端提供 /health 等健康检查端点，可在此处轮询真实状态。
// dark 状态由父组件（App）统一控制并响应 toggle-dark 事件。
// 历史会话已改为左侧常驻栏（HistorySidebar），不再需要弹出按钮。
import { onMounted, ref } from 'vue'

defineProps({ dark: { type: Boolean, default: false } })
defineEmits(['new-chat', 'toggle-dark'])
const sources = ['MySQL', 'ES', 'Qdrant', 'Embed']
const connected = true

/* =========================================================
   跨页退出与登录守门（问数前端 :8173）

   为什么必须问服务端：本套登录体系是纯前端的，会话在 localStorage，
   而 localStorage 按 origin 隔离——:8173 与 :8180 是两个站点，
   在 :8173 里根本读不到 :8180 的登录状态。所以「到底有没有人登录」
   统一问 :8180 的 GET /api/session（由 apps/workbench/server.js 提供）。

   ⚠️ 诚实边界：这是**前端体验级软守门**，不是安全机制。
     · 会话接口可以被 curl 直接 POST 伪造；
     · 本页仍然只是一个前端，改一改就能绕过。
   它防的是「在工作台点了退出，回头打开 8173 还以为登录着」，
   防不住刻意绕过前端的人。真要安全必须做后端鉴权。

   地址一律用 127.0.0.1，不混用 localhost —— 两者是不同 origin，
   混用会让账号库互不可见，误报「邮箱或密码不正确」。
   ========================================================= */
const WORKBENCH_ORIGIN = 'http://127.0.0.1:8180'
const SESSION_API = WORKBENCH_ORIGIN + '/api/session'
const LOGIN_URL = WORKBENCH_ORIGIN + '/login/'
const SESSION_PROBE_MS = 2500

const authUnknown = ref(false)
const authWarnTitle = ref('')

function backToWorkbench() {
  // 子页语义 = 「返回」，只跳页，不清会话（清会话只有工作台首页的「退出登录」做）
  window.location.href = WORKBENCH_ORIGIN + '/'
}

/**
 * 守门策略（本次拍板）：
 *   ok:true                → 放行
 *   ok:false（200 + JSON）  → 明确「没人在登录」→ 跳登录页（fail-closed）
 *   其它（网络错误 / 超时 / 非 2xx / 404 / 返回不是这套接口）→ **fail-open**：
 *     留在本页，只在顶栏提示「无法确认登录态」。
 *   理由：跳过去的目标就是 :8180 —— 它挂了才导致「无法确认」，
 *   此时 fail-closed 等于把一个能正常用的问数页换成一个白屏的登录页，
 *   用户既看不到数据也看不到报错；而误报成本更高（工作台服务未重启时
 *   接口还是 404，全部人都会被挡在门外）。明确读不到结论时宁可放行 + 提示。
 */
async function guardBySharedSession() {
  const hasCtrl = typeof AbortController !== 'undefined'
  const ctrl = hasCtrl ? new AbortController() : null
  const timer = setTimeout(() => { if (ctrl) ctrl.abort() }, SESSION_PROBE_MS)
  let verdict = 'unknown'
  let detail = ''
  try {
    const res = await fetch(SESSION_API, { cache: 'no-store', signal: hasCtrl ? ctrl.signal : undefined })
    if (!res.ok) {
      verdict = 'no-endpoint'
      detail = `工作台会话接口返回 HTTP ${res.status}`
    } else {
      const data = await res.json()
      if (data && data.ok === true) verdict = 'in'
      else if (data && data.ok === false) verdict = 'out'
      else { verdict = 'no-endpoint'; detail = '工作台会话接口返回了无法判读的内容' }
    }
  } catch (e) {
    verdict = 'unreachable'
    detail = '无法连接工作台会话服务 (:8180)'
  } finally {
    clearTimeout(timer)
  }

  if (verdict === 'out') {
    // 明确没登录 → 走登录页；放在 try 里，跳转被拦截也不影响页面继续可用
    try { window.location.replace(LOGIN_URL) } catch (e) { /* 忽略 */ }
    return
  }
  if (verdict === 'in') {
    authUnknown.value = false
    authWarnTitle.value = ''
    return
  }
  authUnknown.value = true
  authWarnTitle.value = `${detail || '工作台未能给出登录结论'}；本页按「放行 + 提示」处理，未强制跳登录页`
}

onMounted(guardBySharedSession)
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

/* 返回工作台：沿用本页胶囊/描边语言（var(--border-strong) + var(--surface)），不新造视觉 */
.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 12px;
  border: 1px solid var(--border-strong);
  border-radius: 999px;
  background: var(--surface);
  color: var(--text-secondary);
  font-size: 12.5px;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.2s ease;
}
.back-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}

/* fail-open 时的诚实提示：用现成的次级文字色 + 描边，不抢眼但不隐瞒。
   窄屏也不隐藏——这是「登录态没验成」的唯一信号，藏起来就等于骗人。 */
.auth-warn {
  font-size: 12px;
  color: var(--text-tertiary);
  border: 1px dashed var(--border-strong);
  border-radius: 999px;
  padding: 2px 9px;
  cursor: help;
  max-width: 42vw;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 640px) {
  .status,
  .kbd-hint {
    display: none;
  }
}
</style>
