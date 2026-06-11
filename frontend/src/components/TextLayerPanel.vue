<script setup lang="ts">
import type { TextLayer } from '@/types'

const props = defineProps<{
  modelValue: TextLayer[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: TextLayer[]]
}>()

function updateLayer(id: string, patch: Partial<TextLayer>) {
  emit('update:modelValue', props.modelValue.map(layer => (
    layer.id === id ? { ...layer, ...patch } : layer
  )))
}

function addLayer() {
  emit('update:modelValue', [
    ...props.modelValue,
    {
      id: crypto.randomUUID(),
      text: '新文字',
      x: 0.5,
      y: 0.5,
      fontSize: 48,
      color: '#111111'
    }
  ])
}

function removeLayer(id: string) {
  emit('update:modelValue', props.modelValue.filter(layer => layer.id !== id))
}
</script>

<template>
  <section class="dk-card p-4 sm:p-5">
    <div class="flex items-center justify-between gap-3 mb-3">
      <h2 class="dk-section-title">文字图层</h2>
      <button type="button" class="dk-btn-ghost text-[12px]" @click="addLayer">添加文字</button>
    </div>

    <div v-if="modelValue.length === 0" class="rounded-xl border border-dashed border-line bg-white p-4 text-[12px] text-ink-muted text-center">
      添加文字后可调整内容、颜色、字号和位置
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="layer in modelValue"
        :key="layer.id"
        class="rounded-xl border border-line bg-white p-3 space-y-3"
      >
        <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
          <input
            :value="layer.text"
            class="dk-input rounded-lg py-1.5"
            @input="updateLayer(layer.id, { text: ($event.target as HTMLInputElement).value })"
          />
          <button type="button" class="dk-btn-ghost text-red-500 shrink-0" @click="removeLayer(layer.id)">删除</button>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <label class="text-[11px] text-ink-muted">
            字号
            <input
              type="number"
              min="12"
              max="240"
              :value="layer.fontSize"
              class="dk-input rounded-lg mt-1 py-1.5"
              @input="updateLayer(layer.id, { fontSize: Number(($event.target as HTMLInputElement).value) })"
            />
          </label>
          <label class="text-[11px] text-ink-muted">
            颜色
            <input
              type="color"
              :value="layer.color"
              class="w-full h-9 rounded-lg border border-line bg-white mt-1"
              @input="updateLayer(layer.id, { color: ($event.target as HTMLInputElement).value })"
            />
          </label>
          <label class="text-[11px] text-ink-muted">
            横向位置 %
            <input
              type="number"
              min="0"
              max="100"
              :value="Math.round(layer.x * 100)"
              class="dk-input rounded-lg mt-1 py-1.5"
              @input="updateLayer(layer.id, { x: Math.min(1, Math.max(0, Number(($event.target as HTMLInputElement).value) / 100)) })"
            />
          </label>
          <label class="text-[11px] text-ink-muted">
            纵向位置 %
            <input
              type="number"
              min="0"
              max="100"
              :value="Math.round(layer.y * 100)"
              class="dk-input rounded-lg mt-1 py-1.5"
              @input="updateLayer(layer.id, { y: Math.min(1, Math.max(0, Number(($event.target as HTMLInputElement).value) / 100)) })"
            />
          </label>
        </div>
      </div>
    </div>
  </section>
</template>
