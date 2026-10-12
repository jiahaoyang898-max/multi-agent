<template>
  <aside class="rail">
    <div class="rail-head">
      <span class="rail-title">搜索流程</span>
    </div>

    <div v-if="!runs.length" class="rail-empty">
      发起一次查询<br />执行流程会在这里实时展示
    </div>

    <div v-else class="runs">
      <div v-for="(run, ri) in runs" :key="ri" class="run-card" :class="{ done: run.done }">
        <div class="run-q" :title="run.q">{{ run.q }}</div>

        <div class="run-sum">
          <template v-if="!run.done">
            <span class="spinner"></span>
            <span class="sum-txt">执行中 {{ run.steps.length }} 步</span>
          </template>
          <template v-else>
            <span class="check">✓</span>
            <span class="sum-txt">已完成 {{ run.steps.length }} 步 · <span class="num">{{ run.totalDur }}s</span></span>
          </template>
        </div>

        <div v-if="run.steps.length" class="steps-list">
          <div
            v-for="(s, si) in run.steps"
            :key="si"
            class="step"
            :class="{ slow: s.dur !== null && s.dur >= 1.5, running: s.dur === null }"
          >
            <span class="sdot"></span>
            <span class="stext">{{ s.text }}</span>
            <span v-if="s.dur !== null" class="sdur num">{{ s.dur }}s</span>
            <span v-else class="sdur run">运行中…</span>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
defineProps({
  /* 仅当前一次: { q, steps:[{text,dur}], totalDur, done }，每次新搜索整体重置 */
  runs: { type: Array, default: () => [] },
})
</script>

<style scoped>
.rail {
  width: 296px;
  flex: 0 0 296px;
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--surface-2);
  border-left: 1px solid var(--border);
}
.rail-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 16px 18px 10px;
}
.rail-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  letter-spacing: 0.01em;
}
.rail-sub {
  font-size: 12px;
  color: var(--text-tertiary);
}
.rail-empty {
  padding: 36px 22px;
  text-align: center;
  color: var(--text-tertiary);
  font-size: 13px;
  line-height: 1.9;
}
.runs {
  flex: 1;
  overflow-y: auto;
  padding: 4px 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.run-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 12px 14px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}
.run-q {
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
  line-height: 1.45;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--border-strong);
}
.run-sum {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0 2px;
  font-size: 12.5px;
  color: var(--text-secondary);
}
.run-sum .check {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(52, 199, 89, 0.14);
  color: #34c759;
  display: grid;
  place-items: center;
  font-size: 10px;
  font-weight: 700;
  flex: 0 0 auto;
}
.spinner {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid var(--accent-soft);
  border-top-color: var(--accent);
  animation: spin 0.8s linear infinite;
  flex: 0 0 auto;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.steps-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
}
.step {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 3px 0;
  font-size: 12.5px;
  color: var(--text);
}
.step .sdot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #34c759;
  flex: 0 0 auto;
}
.step.slow .sdot {
  background: #e8a13c;
}
.step.running .sdot {
  background: var(--accent);
  box-shadow: 0 0 0 4px var(--accent-soft);
  animation: pulse 1s infinite;
}
.step .stext {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.step .sdur {
  font-size: 11.5px;
  color: var(--text-tertiary);
  flex: 0 0 auto;
}
.step.slow .sdur {
  color: #e8a13c;
  font-weight: 600;
}
.step.running .sdur {
  color: var(--accent);
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
@media (max-width: 1180px) {
  .rail {
    display: none;
  }
}
</style>
