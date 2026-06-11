<script setup lang="ts">
import type { TaskMode } from '@/types'

defineProps<{
  modelValue: TaskMode
}>()

const emit = defineEmits<{
  'update:modelValue': [value: TaskMode]
}>()

const modes: Array<{ value: TaskMode; label: string; desc: string }> = [
  { value: 'general', label: '通用编辑', desc: '整图理解和常规修改' },
  { value: 'local_edit', label: '局部修改', desc: '先涂抹区域再让 AI 修改' },
  { value: 'text_layer', label: '修改文字', desc: '用可控文字图层合成' }
]
</script>

<template>
  <section class="dk-card p-4 sm:p-5">
    <div class="flex items-center justify-between gap-3 mb-3">
      <h2 class="dk-section-title">编辑方式</h2>
      <span class="text-[12px] text-ink-faint">先选择工作流</span>
    </div>

    <div class="grid grid-cols-3 gap-1.5 sm:gap-2">
      <button
        v-for="mode in modes"
        :key="mode.value"
        type="button"
        class="rounded-xl border px-2 py-2.5 text-center transition-all sm:p-3 sm:text-left"
        :class="modelValue === mode.value
          ? 'border-brand bg-brand-50/70 shadow-sm'
          : 'border-line bg-white hover:border-brand/40'"
        @click="emit('update:modelValue', mode.value)"
      >
        <div class="text-[13px] font-semibold text-ink leading-tight">{{ mode.label }}</div>
        <div class="hidden sm:block text-[11px] text-ink-muted mt-1 leading-[16px]">{{ mode.desc }}</div>
      </button>
    </div>
  </section>
</template>
