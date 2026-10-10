<template>
  <div v-if="chart" class="chart">
    <div class="chart-title">{{ chart.labelCol }} · {{ chart.numCol }}</div>
    <div class="bars">
      <div v-for="(d, i) in chart.data" :key="i" class="bar-col">
        <div class="bar-track">
          <div class="bar-fill" :style="{ height: d.pct + '%' }"></div>
        </div>
        <div class="bar-val">{{ formatVal(d.value) }}</div>
        <div class="bar-label">{{ d.label }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  rows: { type: Array, default: () => [] },
})

function isNum(v) {
  return typeof v === 'number' && !isNaN(v)
}

// 自动从结果表中挑「标签列 + 数值列」绘制柱状趋势图，不依赖任何后端字段名。
const chart = computed(() => {
  const rows = props.rows || []
  if (!rows.length) return null
  const cols = Object.keys(rows[0] || {})
  if (cols.length < 2) return null

  const numCol = cols.find((c) => rows.every((r) => isNum(r[c])))
  if (!numCol) return null
  const labelCol = cols.find((c) => c !== numCol) || cols[0]

  const data = rows.slice(0, 8).map((r) => ({
    label: String(r[labelCol]),
    value: Number(r[numCol]) || 0,
  }))
  const max = Math.max(...data.map((d) => d.value), 1)

  return {
    numCol,
    labelCol,
    data: data.map((d) => ({ ...d, pct: Math.max(4, Math.round((d.value / max) * 100)) })),
  }
})

function formatVal(v) {
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(1) + '亿'
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(1) + '万'
  return String(v)
}
</script>

<style scoped>
.chart {
  margin-top: 14px;
  padding: 14px 16px;
  border-top: 1px dashed var(--border-strong);
}
.chart-title {
  font-size: 12.5px;
  color: var(--text-tertiary);
  margin-bottom: 14px;
}
.bars {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  height: 140px;
}
.bar-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  height: 100%;
  min-width: 0;
}
.bar-track {
  width: 100%;
  max-width: 36px;
  flex: 1;
  display: flex;
  align-items: flex-end;
}
.bar-fill {
  width: 100%;
  border-radius: 6px 6px 2px 2px;
  background: linear-gradient(180deg, var(--accent), #8fb4d8);
  transition: height 0.5s cubic-bezier(0.22, 0.61, 0.36, 1);
}
.bar-val {
  font-size: 11px;
  color: var(--text-secondary);
  margin: 6px 0 2px;
  white-space: nowrap;
}
.bar-label {
  font-size: 11px;
  color: var(--text-tertiary);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
