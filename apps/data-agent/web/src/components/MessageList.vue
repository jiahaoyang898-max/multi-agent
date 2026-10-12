<template>
  <div class="messages">
    <div v-for="(m, i) in messages" :key="i" class="row" :class="m.role">
      <div v-if="m.role === 'assistant'" class="avatar">🤖</div>

      <div class="bubble" :class="m.type">
        <!-- 纯文本 -->
        <div v-if="m.type === 'text'">{{ m.content }}</div>

        <!-- 结果：KPI 大数卡 / 表格 + 图表 -->
        <div v-else-if="m.type === 'table'">
          <!-- 单行单值 → KPI 大数卡 -->
          <div v-if="isKpi(m)" class="kpi">
            <span class="kpi-name">{{ m.columns[0] }}</span>
            <span class="kpi-val num">{{ formatVal(m.rows[0][m.columns[0]], m.columns[0]) }}</span>
          </div>

          <template v-else>
            <div class="toolbar">
              <div class="seg">
                <button :class="{ on: m.view !== 'chart' }" @click="m.view = 'table'">表格</button>
                <button :class="{ on: m.view === 'chart' }" @click="m.view = 'chart'">图表</button>
              </div>
              <button class="tbtn" @click="$emit('copy', m)">复制</button>
              <button class="tbtn" @click="$emit('export', m)">导出 CSV</button>
            </div>

            <div v-show="m.view !== 'chart'" class="table-wrap">
              <table class="result-table">
                <thead>
                  <tr>
                    <th v-for="col in m.columns" :key="col" :class="{ num: isNumCol(m, col) }">{{ col }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, ri) in m.rows" :key="ri">
                    <td
                      v-for="col in m.columns"
                      :key="col"
                      :class="{ num: isNumCol(m, col), hl: isNumCol(m, col) && m.rows.length === 1 }"
                    >
                      {{ formatVal(row[col], col) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div v-show="m.view === 'chart'" class="hbars">
              <div v-for="row in m.rows.slice(0, 12)" :key="chartKey(m, row)" class="hbar">
                <span class="lbl">{{ labelOf(m, row) }}</span>
                <div class="track">
                  <div class="fill" :style="{ width: pctOf(m, row) + '%' }"></div>
                </div>
                <span class="v num">{{ formatVal(valueOf(m, row), valueCol(m)) }}</span>
              </div>
            </div>
          </template>

          <div v-if="isEmpty(m.rows)" class="empty-hint">
            查询成功，但该条件下没有匹配到任何数据行，可尝试换个时间范围（如 2025 年 1 月 ~ 3 月）
          </div>

          <div v-if="m.followups && m.followups.length" class="followups">
            <button
              v-for="(f, fi) in m.followups"
              :key="fi"
              class="fchip"
              @click="$emit('send', f.q)"
            >
              <span class="arr">↳</span>{{ f.label }}
            </button>
          </div>
        </div>

        <!-- 错误 + 重试 -->
        <div v-else-if="m.type === 'error'" class="error-box">
          <span class="err-ic">!</span>
          <span class="err-txt">{{ m.content }}</span>
          <button v-if="m.retry" class="retry" @click="$emit('retry', m.retry)">重试</button>
        </div>
      </div>

      <div v-if="m.role === 'user'" class="avatar user">🧑</div>
    </div>
    <div class="bottom-spacer"></div>
  </div>
</template>

<script setup>
const props = defineProps({
  messages: { type: Array, default: () => [] },
})
defineEmits(['send', 'retry', 'copy', 'export'])

const MONEY = /(销售额|金额|gmv|sales|revenue|总价|总额|total|price|cost)/i

function isNum(v) {
  return typeof v === 'number' && !isNaN(v)
}
// 单行且所有列均为数值 → KPI 大数卡；否则走表格/图表
function isKpi(m) {
  return m.rows.length === 1 && m.columns.every((c) => isNum(m.rows[0][c]))
}
function isEmpty(rows) {
  if (!rows || !rows.length) return true
  return rows.every((r) => Object.values(r).every((v) => v === null || v === undefined))
}
function isNumCol(m, col) {
  return m.rows.some((r) => isNum(r[col]))
}
function formatVal(v, name) {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') {
    const money = MONEY.test(name || '')
    const s = v.toLocaleString('en-US')
    return money ? '¥' + s : s
  }
  return String(v)
}

/* 图表：挑数值列 + 标签列 */
function valueCol(m) {
  const cols = m.columns
  return cols.find((c) => m.rows.every((r) => isNum(r[c]))) || cols[0]
}
function labelCol(m) {
  const vc = valueCol(m)
  return m.columns.find((c) => c !== vc) || m.columns[0]
}
function valueOf(m, row) {
  return Number(row[valueCol(m)]) || 0
}
function labelOf(m, row) {
  return String(row[labelCol(m)])
}
function chartKey(m, row) {
  return labelOf(m, row) + '-' + valueOf(m, row)
}
function pctOf(m, row) {
  const vals = m.rows.map((r) => Math.abs(Number(r[valueCol(m)]) || 0))
  const max = Math.max(...vals, 1)
  return Math.max(4, Math.round((Math.abs(valueOf(m, row)) / max) * 100))
}
</script>

<style scoped>
.messages {
  height: 100%;
  overflow-y: auto;
  padding: 24px max(20px, calc((100% - var(--maxw)) / 2)) 160px;
}
.row {
  display: flex;
  margin-bottom: 18px;
  align-items: flex-start;
}
.row.assistant {
  justify-content: flex-start;
}
.row.user {
  justify-content: flex-end;
}
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 11px;
  background: var(--accent-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  margin: 0 12px;
  flex: 0 0 auto;
}
.avatar.user {
  background: linear-gradient(135deg, var(--accent), #7aa3cf);
}
.bubble {
  max-width: min(760px, 76%);
  padding: 14px 16px;
  border-radius: 18px;
  background: var(--surface);
  box-shadow: var(--shadow-soft);
  font-size: 15px;
  line-height: 1.6;
}
.row.user .bubble {
  background: var(--accent);
  color: #fff;
  border-bottom-right-radius: 6px;
}
.row.assistant .bubble {
  border-bottom-left-radius: 6px;
}

/* KPI 大数卡 */
.kpi {
  display: flex;
  align-items: baseline;
  gap: 14px;
  padding: 18px 22px;
  margin: 4px 0;
  background: linear-gradient(160deg, var(--accent-soft), var(--surface-2) 70%);
  border: 1px solid var(--border-strong);
  border-radius: 14px;
}
.kpi-name {
  font-size: 13px;
  color: var(--text-secondary);
}
.kpi-val {
  font-size: 38px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--accent-deep);
}

/* 结果工具条 */
.toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 12px 0 8px;
}
.seg {
  display: inline-flex;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 9px;
  padding: 2px;
}
.seg button {
  border: none;
  background: transparent;
  padding: 5px 14px;
  border-radius: 7px;
  font-size: 12.5px;
  color: var(--text-secondary);
  cursor: pointer;
}
.seg button.on {
  background: var(--surface);
  color: var(--text);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}
.tbtn {
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-secondary);
  border-radius: 9px;
  padding: 5px 12px;
  font-size: 12.5px;
  cursor: pointer;
}
.tbtn:hover {
  border-color: var(--accent);
  color: var(--accent);
}

/* 表格 */
.table-wrap {
  max-width: 100%;
  overflow-x: auto;
  margin-bottom: 6px;
}
.result-table {
  width: max-content;
  min-width: 100%;
  border-collapse: collapse;
}
.result-table th,
.result-table td {
  border: 1px solid var(--border-strong);
  padding: 8px 14px;
  white-space: nowrap;
  font-size: 13.5px;
  text-align: left;
}
.result-table th {
  background: var(--surface-2);
  font-weight: 600;
  position: sticky;
  top: 0;
}
.result-table td.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.result-table th.num {
  text-align: right;
}
.result-table td.hl {
  color: var(--accent-deep);
  font-weight: 600;
}

/* 横向条形图 */
.hbars {
  margin: 6px 0;
}
.hbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 5px 0;
}
.hbar .lbl {
  width: 92px;
  font-size: 13px;
  color: var(--text-secondary);
  text-align: right;
  flex: 0 0 auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hbar .track {
  flex: 1;
  height: 18px;
  background: var(--surface-2);
  border-radius: 6px;
  overflow: hidden;
}
.hbar .fill {
  height: 100%;
  border-radius: 6px;
  background: linear-gradient(90deg, var(--accent), #8fb4d8);
  transition: width 0.5s cubic-bezier(0.22, 0.61, 0.36, 1);
}
.hbar .v {
  width: 92px;
  font-size: 12.5px;
  color: var(--text);
  flex: 0 0 auto;
}

/* 空结果提示 */
.empty-hint {
  margin-top: 8px;
  font-size: 12.5px;
  color: var(--text-tertiary);
  background: var(--surface-2);
  border-radius: 8px;
  padding: 8px 12px;
}

/* 智能追问 */
.followups {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}
.fchip {
  border: 1px solid var(--border-strong);
  background: var(--surface);
  border-radius: 999px;
  padding: 6px 14px;
  font-size: 12.5px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}
.fchip:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-soft);
}
.fchip .arr {
  color: var(--accent);
  margin-right: 5px;
}

/* 错误 */
.error-box {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #ff3b30;
  font-weight: 500;
}
.err-ic {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #ff3b30;
  color: #fff;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  flex: 0 0 auto;
}
.err-txt {
  flex: 1;
}
.retry {
  border: 1px solid #ff3b30;
  background: transparent;
  color: #ff3b30;
  border-radius: 8px;
  padding: 3px 12px;
  font-size: 12.5px;
  cursor: pointer;
  flex: 0 0 auto;
}
.retry:hover {
  background: rgba(255, 59, 48, 0.08);
}

.bottom-spacer {
  height: 40px;
}
@media (max-width: 640px) {
  .messages {
    padding: 18px 14px 160px;
  }
  .bubble {
    max-width: 82%;
  }
}
</style>
