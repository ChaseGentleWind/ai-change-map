<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'

defineProps<{ src: string; title: string }>()
const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLDialogElement | null>(null)
const actualSize = ref(false)
const dimensions = ref('')
const failed = ref(false)
let previousOverflow = ''

function imageLoaded(event: Event) {
  const image = event.target as HTMLImageElement
  dimensions.value = `${image.naturalWidth} × ${image.naturalHeight}`
}

onMounted(() => {
  previousOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  dialog.value?.showModal()
})

onBeforeUnmount(() => {
  document.body.style.overflow = previousOverflow
  dialog.value?.close()
})
</script>

<template>
  <dialog ref="dialog" class="image-lightbox" aria-labelledby="preview-title"
    @cancel.prevent="emit('close')" @click="($event.target === $event.currentTarget) && emit('close')">
    <div class="lightbox-content">
      <header class="lightbox-toolbar">
        <div class="min-w-0">
          <h2 id="preview-title" class="truncate text-sm font-semibold">{{ title }}</h2>
          <p class="text-xs text-slate-400 mt-1">{{ dimensions || '加载图片中…' }}</p>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <button type="button" class="viewer-button" :aria-pressed="actualSize" @click="actualSize = !actualSize">
            {{ actualSize ? '适应窗口' : '查看原尺寸' }}
          </button>
          <button type="button" class="viewer-button" aria-label="关闭图片预览" @click="emit('close')">关闭 ×</button>
        </div>
      </header>
      <div class="lightbox-stage" :class="{ 'actual-size': actualSize }">
        <p v-if="failed" role="alert" class="text-sm text-white">图片加载失败，请关闭后重试</p>
        <img v-else :src="src" :alt="title" @load="imageLoaded" @error="failed = true"
          @dblclick="actualSize = !actualSize" />
      </div>
      <footer class="text-center text-xs text-slate-400 py-2">双击切换原尺寸 · Esc 关闭</footer>
    </div>
  </dialog>
</template>

<style scoped>
.image-lightbox { padding: 0; border: 0; border-radius: 16px; width: 94vw; max-width: 1600px; height: 92dvh; max-height: 100dvh; background: #111827; color: white; overflow: hidden; }
.image-lightbox::backdrop { background: rgb(15 23 42 / .78); backdrop-filter: blur(6px); }
.lightbox-content { display: grid; grid-template-rows: auto minmax(0, 1fr) auto; height: 100%; }
.lightbox-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 20px; border-bottom: 1px solid #ffffff18; }
.viewer-button { font-size: 12px; padding: 8px 12px; border: 1px solid #ffffff30; border-radius: 8px; }
.viewer-button:hover { background: #ffffff18; }
.lightbox-stage { min-height: 0; overflow: auto; display: flex; align-items: center; justify-content: center; padding: 16px; }
.lightbox-stage img { max-width: 100%; max-height: 100%; object-fit: contain; cursor: zoom-in; }
.lightbox-stage.actual-size { display: block; }
.lightbox-stage.actual-size img { max-width: none; max-height: none; margin: auto; cursor: zoom-out; }
@media (max-width: 520px) { .lightbox-toolbar { padding: 12px; gap: 8px; } .viewer-button { padding: 8px; } }
</style>
