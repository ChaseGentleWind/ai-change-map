<script setup lang="ts">
import { ref, computed, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { editImage, getSession } from '@/api'
import ImageCanvasEditor from '@/components/ImageCanvasEditor.vue'
import TaskModePanel from '@/components/TaskModePanel.vue'
import ImageLightbox from '@/components/ImageLightbox.vue'
import type { EditMetadata, EditRecord, TaskMode, TextLayer } from '@/types'

const route = useRoute()
const router = useRouter()

// 状态
const mainImage = ref<File | null>(null)
const mainImagePreview = ref<string>('')
const referenceImages = ref<File[]>([])
const referenceImagePreviews = ref<string[]>([])
const instruction = ref('')
const outputCount = ref(1)
const advancedSettingsOpen = ref(false)
const selectedProvider = ref('openai_1k')
const selectedResolution = ref('1k')
const modelOptions = [
  { provider: 'openai_reverse_1k', model: 'gpt-image-2-逆向', label: 'GPT Image 2 逆向', price: 0.04, quality: '默认', resolutions: ['1k'] },
  { provider: 'openai_reverse_4k', model: 'gpt-image-2.5-逆向', label: 'GPT Image 2.5 逆向', price: 0.04, quality: '默认', resolutions: ['1k', '2k', '4k'] },
  { provider: 'openai_1k', model: 'gpt-image-2-1k', label: 'GPT Image 2 · 1K', price: 0.06, quality: '默认 · 速度快', resolutions: ['1k'] },
  { provider: 'openai_sunburst_1k', model: 'gpt-image-2.5-sunburst-1k', label: 'Sunburst · 1K', price: 0.06, quality: '默认 · 速度快', resolutions: ['1k'] },
  { provider: 'openai_flare_1k', model: 'gpt-image-2.5-flare-1k', label: 'Flare · 1K', price: 0.06, quality: '默认 · 速度快', resolutions: ['1k'] },
  { provider: 'openai_4k', model: 'gpt-image-2-4k', label: 'GPT Image 2 · 4K', price: 0.12, quality: '中等', resolutions: ['1k', '2k', '4k'] },
  { provider: 'openai_4k_high', model: 'gpt-image-2-4k-high', label: 'GPT Image 2 · 4K High', price: 0.20, quality: '高', resolutions: ['4k'] },
  { provider: 'openai_flare_4k_max', model: 'gpt-image-2.5-flare-4k-max', label: 'Flare · 4K Max', price: 0.30, quality: 'Max', resolutions: ['4k'] },
  { provider: 'openai_sunburst_4k_max', model: 'gpt-image-2.5-sunburst-4k-max', label: 'Sunburst · 4K Max', price: 0.40, quality: 'Max', resolutions: ['4k'] }
] as const
const selectedModel = computed(() => modelOptions.find(option => option.provider === selectedProvider.value) || modelOptions[2])
const resolutionOptions = computed(() => selectedModel.value.resolutions)
watch(selectedProvider, () => {
  if (!resolutionOptions.value.includes(selectedResolution.value as never)) {
    selectedResolution.value = resolutionOptions.value[0]
  }
}, { flush: 'sync' })
const taskMode = ref<TaskMode>('general')
const textLayers = ref<TextLayer[]>([])
const brushSize = ref(48)
const maskTool = ref<'paint' | 'erase'>('paint')
const maskFeather = ref(4)
const textTool = ref<'select' | 'erase'>('select')
const maskPreviewUrl = ref('')
const canvasEditor = ref<InstanceType<typeof ImageCanvasEditor> | null>(null)

// 会话状态
const sessionId = ref<string>('')
const chatHistory = ref<EditRecord[]>([])
const currentParentId = ref<number | null>(null)
const currentParentResultIndex = ref(0)
const selectedRecordId = ref<number | null>(null)
const workspaceTab = ref<'results' | 'canvas'>('results')
const lightbox = ref<{ url: string; title: string } | null>(null)
const selectedRecord = computed(() => chatHistory.value.find(record => record.id === selectedRecordId.value))
const selectedRound = computed(() => chatHistory.value.findIndex(record => record.id === selectedRecordId.value) + 1)
const sourceRecord = computed(() => chatHistory.value.find(record => record.id === currentParentId.value))
const sourceRound = computed(() => chatHistory.value.findIndex(record => record.id === currentParentId.value) + 1)
const editingImagePreview = computed(() => sourceRecord.value?.result_urls?.[currentParentResultIndex.value] || mainImagePreview.value)
const sourceLabel = computed(() => currentParentId.value
  ? `第 ${sourceRound.value} 轮 · 结果 ${currentParentResultIndex.value + 1}`
  : '上传的原图')

watch(taskMode, mode => { workspaceTab.value = mode === 'general' ? 'results' : 'canvas' }, { flush: 'sync' })

function viewImage(url: string, title: string) {
  lightbox.value = { url, title }
}

function useOriginal() {
  currentParentId.value = null
  currentParentResultIndex.value = 0
  maskPreviewUrl.value = ''
  textLayers.value = []
  void canvasEditor.value?.clearMask()
}

// 加载状态
const loading = ref(false)
const sessionLoading = ref(false)
const error = ref('')
const elapsedSeconds = ref(0)
let timer: ReturnType<typeof setInterval> | null = null
let sessionLoadToken = 0

// 进度提示文案
const loadingHint = computed(() => {
  const s = elapsedSeconds.value
  if (s < 10) return 'AI 正在理解图片内容...'
  if (s < 30) return '正在生成编辑结果...'
  if (s < 60) return '图像渲染中，稍等片刻...'
  return '快好了，图像生成需要一点时间...'
})

function startTimer() {
  elapsedSeconds.value = 0
  timer = setInterval(() => { elapsedSeconds.value++ }, 1000)
}

function stopTimer() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  elapsedSeconds.value = 0
}

onUnmounted(() => stopTimer())

// 拖拽状态
const isDragging = ref(false)
const isReferenceDragging = ref(false)

// 计算属性
const canSubmit = computed(() => {
  const hasInstruction = instruction.value.trim().length > 0
  const hasTextLayer = taskMode.value === 'text_layer' && textLayers.value.length > 0
  return mainImage.value && (hasInstruction || hasTextLayer) && !loading.value && !sessionLoading.value
})
watch(
  () => route.query.sessionId,
  (id) => {
    if (typeof id === 'string' && id) {
      loadSessionDetail(id)
    }
  },
  { immediate: true }
)

async function loadSessionDetail(id: string) {
  const token = ++sessionLoadToken
  sessionLoading.value = true
  error.value = ''

  try {
    const data = await getSession(id)
    const originalFile = await fileFromUrl(data.original_url, 'original_image.png')

    if (token !== sessionLoadToken) return

    sessionId.value = data.id
    mainImage.value = originalFile
    mainImagePreview.value = data.original_url
    referenceImagePreviews.value.forEach(url => URL.revokeObjectURL(url))
    referenceImages.value = []
    referenceImagePreviews.value = []
    instruction.value = ''
    chatHistory.value = data.records

    const lastRecord = data.records[data.records.length - 1]
    const metadata = lastRecord?.edit_metadata
    taskMode.value = metadata?.task_mode === 'local_edit' ? 'local_edit' : 'general'
    // 历史结果已包含文字和局部修改，继续编辑时从空图层、空遮罩开始。
    textLayers.value = []
    brushSize.value = metadata?.mask?.brushSize || 48
    maskFeather.value = metadata?.mask?.feather ?? 4
    maskTool.value = 'paint'
    textTool.value = 'select'
    maskPreviewUrl.value = ''
    currentParentId.value = lastRecord?.id ?? null
    currentParentResultIndex.value = 0
    selectedRecordId.value = lastRecord?.id ?? null
    workspaceTab.value = 'results'
    selectedProvider.value = metadata?.model_selection?.provider || 'openai_1k'
    selectedResolution.value = metadata?.model_selection?.resolution || '1k'
  } catch (e: any) {
    if (token === sessionLoadToken) {
      error.value = e.message || '加载历史会话失败'
    }
  } finally {
    if (token === sessionLoadToken) {
      sessionLoading.value = false
    }
  }
}

async function fileFromUrl(url: string, filename: string) {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error('历史图片加载失败')
  }

  const blob = await response.blob()
  return new File([blob], filename, { type: blob.type || 'image/png' })
}

// 处理主图上传
function handleMainImageChange(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files && input.files[0]) {
    setMainImage(input.files[0])
  }
  input.value = ''
}

function setMainImage(file: File) {
  if (loading.value || sessionLoading.value) return
  if (!file.type.startsWith('image/') || file.size > 20 * 1024 * 1024) {
    error.value = '请上传 20MB 以内的图片'
    return
  }
  reset()
  const token = sessionLoadToken
  mainImage.value = file
  const reader = new FileReader()
  reader.onload = (e) => {
    if (token !== sessionLoadToken) return
    mainImagePreview.value = e.target?.result as string
  }
  reader.readAsDataURL(file)
  void canvasEditor.value?.clearMask()
}

// 处理参考图上传
function handleReferenceImageChange(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files) addReferenceImages(input.files)
  input.value = ''
}

function addReferenceImages(files: File[] | FileList) {
  if (loading.value || sessionLoading.value) return
  Array.from(files)
    .filter(file => file.type.startsWith('image/'))
    .forEach(file => {
      if (file.size > 20 * 1024 * 1024) {
        error.value = '参考图需小于 20MB'
        return
      }
      referenceImages.value.push(file)
      referenceImagePreviews.value.push(URL.createObjectURL(file))
    })
}

function removeReferenceImage(index: number) {
  const preview = referenceImagePreviews.value[index]
  if (preview) URL.revokeObjectURL(preview)
  referenceImages.value.splice(index, 1)
  referenceImagePreviews.value.splice(index, 1)
}

// 拖拽上传
function handleDragOver(event: DragEvent) {
  event.preventDefault()
  isDragging.value = true
}

function handleDragLeave() {
  isDragging.value = false
}

function handleDrop(event: DragEvent) {
  event.preventDefault()
  isDragging.value = false
  const files = event.dataTransfer?.files
  if (files && files[0]?.type.startsWith('image/')) {
    setMainImage(files[0])
  }
}

function handleReferenceDragOver(event: DragEvent) {
  event.preventDefault()
  isReferenceDragging.value = true
}

function handleReferenceDragLeave() {
  isReferenceDragging.value = false
}

function handleReferenceDrop(event: DragEvent) {
  event.preventDefault()
  isReferenceDragging.value = false
  const files = event.dataTransfer?.files
  if (files) addReferenceImages(files)
}

// 提交编辑
async function submitEdit() {
  if (!canSubmit.value) return

  loading.value = true
  error.value = ''
  startTimer()

  try {
    const metadata: EditMetadata = {
      task_mode: taskMode.value,
      text_layers: textLayers.value,
      mask: { brushSize: brushSize.value, feather: maskFeather.value },
      model_selection: {
        provider: selectedProvider.value,
        model: selectedModel.value.model,
        resolution: selectedResolution.value,
        price_per_image: selectedModel.value.price
      }
    }
    const mainImageForSubmit = taskMode.value === 'text_layer' && canvasEditor.value
      ? await canvasEditor.value.exportCompositeImage()
      : mainImage.value!
    const maskImage = (taskMode.value === 'local_edit' || taskMode.value === 'text_layer') && canvasEditor.value
      ? await canvasEditor.value.exportMaskImage()
      : null
    const instructionText = instruction.value.trim() || '修改文字图层'
    const submittedSource = editingImagePreview.value
    const submittedParentId = currentParentId.value

    const result = await editImage(
      mainImageForSubmit,
      instructionText,
      {
        sessionId: sessionId.value || undefined,
        parentId: currentParentId.value || undefined,
        parentResultIndex: currentParentId.value ? currentParentResultIndex.value : undefined,
        taskMode: taskMode.value,
        maskImage: maskImage || undefined,
        editMetadata: metadata,
        outputCount: outputCount.value,
        referenceImages: referenceImages.value.length > 0 ? referenceImages.value : undefined,
        provider: selectedProvider.value,
        outputResolution: selectedResolution.value
      }
    )

    sessionId.value = result.session_id
    currentParentId.value = result.record_id
    currentParentResultIndex.value = 0

    chatHistory.value.push({
      id: result.record_id,
      session_id: result.session_id,
      main_image_url: submittedSource,
      parent_id: submittedParentId || undefined,
      instruction: instructionText,
      task_type: result.task_type,
      provider: result.provider,
      model: result.model,
      fallback_used: result.fallback_used,
      result_urls: result.results,
      edit_metadata: metadata,
      status: 'completed',
      cost: result.cost,
      cost_currency: result.cost_currency,
      duration_ms: result.duration_ms,
      created_at: new Date().toISOString()
    })

    instruction.value = ''
    selectedRecordId.value = result.record_id
    workspaceTab.value = 'results'
    maskPreviewUrl.value = ''
    textLayers.value = []
    void canvasEditor.value?.clearMask()

  } catch (e: any) {
    error.value = e.message || '编辑失败，请重试'
  } finally {
    loading.value = false
    stopTimer()
  }
}

// 从历史某张结果图继续编辑
function continueFromRecord(record: EditRecord, resultIndex: number = 0) {
  if (loading.value || !record.result_urls?.[resultIndex]) return
  currentParentId.value = record.id
  currentParentResultIndex.value = resultIndex
  textLayers.value = []
  maskPreviewUrl.value = ''
  void canvasEditor.value?.clearMask()
  if (taskMode.value !== 'general') workspaceTab.value = 'canvas'
}

// 下载图片
function downloadImage(url: string) {
  const a = document.createElement('a')
  a.href = url
  a.download = `ai-edit-${Date.now()}.png`
  a.click()
}

// 重置
function reset() {
  if (loading.value) return
  sessionLoadToken++
  referenceImagePreviews.value.forEach(url => URL.revokeObjectURL(url))
  mainImage.value = null
  mainImagePreview.value = ''
  referenceImages.value = []
  referenceImagePreviews.value = []
  isDragging.value = false
  isReferenceDragging.value = false
  instruction.value = ''
  sessionId.value = ''
  chatHistory.value = []
  selectedRecordId.value = null
  workspaceTab.value = 'results'
  lightbox.value = null
  selectedProvider.value = 'openai_1k'
  selectedResolution.value = '1k'
  advancedSettingsOpen.value = false
  currentParentId.value = null
  currentParentResultIndex.value = 0
  taskMode.value = 'general'
  textLayers.value = []
  brushSize.value = 48
  maskTool.value = 'paint'
  maskFeather.value = 4
  textTool.value = 'select'
  maskPreviewUrl.value = ''
  error.value = ''
  if (route.query.sessionId) {
    void router.replace({ path: '/' })
  }
}

onUnmounted(() => referenceImagePreviews.value.forEach(url => URL.revokeObjectURL(url)))

</script>

<template>
  <div class="editor-page">
    <header class="editor-header">
      <div>
        <h1 class="text-lg font-semibold text-ink">图像编辑工作台</h1>
        <p class="text-xs text-ink-muted mt-1">保留原图，逐步完善每一次修改</p>
      </div>
      <button type="button" class="dk-btn-ghost border border-line bg-white text-xs" :disabled="loading || sessionLoading" @click="reset">新建编辑</button>
    </header>

    <div class="editor-layout">
      <fieldset class="control-pane" :disabled="loading || sessionLoading">
        <legend class="sr-only">图片与编辑设置</legend>
        <section>
          <div class="section-heading">
            <h2>原图</h2>
            <span>JPG / PNG / WebP · ≤ 20MB</span>
          </div>
          <input ref="mainImageInput" type="file" accept="image/*" class="hidden" aria-label="上传原图" @change="handleMainImageChange" />
          <div class="original-drop" :class="{ dragging: isDragging }"
            @dragover="handleDragOver" @dragleave="handleDragLeave" @drop="handleDrop">
            <template v-if="mainImagePreview">
              <button type="button" class="original-preview preview-surface" aria-label="放大查看原图" @click="viewImage(mainImagePreview, '原图')">
                <img :src="mainImagePreview" alt="上传的原图" />
                <span class="zoom-hint">放大 ↗</span>
              </button>
              <div class="min-w-0 flex-1 py-2">
                <p class="text-xs font-medium text-ink truncate" :title="mainImage?.name">{{ mainImage?.name }}</p>
                <p class="text-[11px] text-ink-muted mt-1.5">始终保留上传时的原图</p>
                <button type="button" class="text-xs text-brand mt-3 hover:underline" @click="($refs.mainImageInput as HTMLInputElement).click()">更换图片</button>
              </div>
            </template>
            <button v-else type="button" class="upload-placeholder" @click="($refs.mainImageInput as HTMLInputElement).click()">
              <svg class="w-7 h-7 text-brand mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 8 12 3.5 7.5 8M12 3.5V16"/>
              </svg>
              <span class="text-sm font-medium">点击或拖拽上传原图</span>
              <span class="text-xs text-ink-muted mt-1">从一张图片开始</span>
            </button>
          </div>

          <div class="section-heading mt-4">
            <h3>参考图 <span class="font-normal">（可选）</span></h3>
            <span>{{ referenceImagePreviews.length ? referenceImagePreviews.length + ' 张' : '支持多张、拖拽添加' }}</span>
          </div>
          <div class="reference-grid" :class="{ dragging: isReferenceDragging }"
            @dragover="handleReferenceDragOver" @dragleave="handleReferenceDragLeave" @drop="handleReferenceDrop">
            <div v-for="(preview, index) in referenceImagePreviews" :key="preview" class="reference-tile">
              <button type="button" class="reference-preview preview-surface" :aria-label="`放大查看参考图 ${index + 1}`" @click="viewImage(preview, `参考图 ${index + 1}`)">
                <img :src="preview" :alt="`参考图 ${index + 1}`" />
              </button>
              <button type="button" class="remove-reference" :aria-label="`移除参考图 ${index + 1}`" @click="removeReferenceImage(index)">×</button>
            </div>
            <label class="reference-add">
              <span class="text-xl font-light leading-none">＋</span>
              <span>添加参考</span>
              <input type="file" accept="image/*" multiple class="sr-only" aria-label="添加参考图" @change="handleReferenceImageChange" />
            </label>
          </div>
        </section>

        <TaskModePanel v-model="taskMode" />
        <section class="instruction-panel">
          <div class="section-heading">
            <h2>编辑指令</h2>
            <span>Ctrl + Enter</span>
          </div>
          <textarea v-model="instruction" class="dk-textarea text-[13px]" rows="4" aria-label="编辑指令"
            placeholder="描述你想修改的内容，例如：换成蓝色背景，保持人物不变…" @keydown.ctrl.enter="submitEdit" />
          <div class="submission-source">
            <img v-if="editingImagePreview" :src="editingImagePreview" alt="" />
            <div class="min-w-0">
              <span class="text-[10px] text-ink-muted block">本次编辑基于</span>
              <span class="text-xs font-medium text-ink">{{ mainImagePreview ? sourceLabel : '请先上传原图' }}</span>
            </div>
            <button v-if="currentParentId" type="button" class="text-xs text-brand ml-auto shrink-0" @click="useOriginal">改用原图</button>
          </div>
          <section class="advanced-settings">
            <button type="button" class="advanced-toggle" :aria-expanded="advancedSettingsOpen" @click="advancedSettingsOpen = !advancedSettingsOpen">
              <span class="flex items-center gap-2"><svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.8"><path stroke-linecap="round" stroke-linejoin="round" d="M10.5 6h10.75M10.5 6a2.25 2.25 0 1 1-4.5 0m4.5 0a2.25 2.25 0 1 0-4.5 0m-1.5 0H2.75m13.5 12H21m-4.5 0a2.25 2.25 0 1 1-4.5 0m4.5 0a2.25 2.25 0 1 0-4.5 0m-1.5 0H2.75"/></svg>高级设置</span>
              <span class="flex items-center gap-2"><span>{{ selectedModel.label }} · {{ selectedResolution.toUpperCase() }}</span><span class="advanced-chevron" :class="{ open: advancedSettingsOpen }">⌄</span></span>
            </button>
            <div v-if="advancedSettingsOpen" class="advanced-content">
              <label class="setting-label" for="image-model">生成模型</label>
              <select id="image-model" v-model="selectedProvider" class="setting-select">
                <option v-for="option in modelOptions" :key="option.provider" :value="option.provider">
                  {{ option.label }} · ¥{{ option.price.toFixed(2) }}/张
                </option>
              </select>
              <p class="model-detail"><span>{{ selectedModel.model }}</span><span>{{ selectedModel.quality }}</span></p>
              <div class="resolution-row">
                <label v-if="resolutionOptions.length > 1" class="setting-label" for="output-resolution">输出分辨率</label>
                <label v-else class="setting-label">输出分辨率</label>
                <select v-if="resolutionOptions.length > 1" id="output-resolution" v-model="selectedResolution" class="resolution-select">
                  <option v-for="resolution in resolutionOptions" :key="resolution" :value="resolution">{{ resolution.toUpperCase() }}</option>
                </select>
                <span v-else class="fixed-resolution">{{ selectedResolution.toUpperCase() }} 固定</span>
              </div>
              <div class="price-summary">
                <span>参考价格 <strong>¥{{ selectedModel.price.toFixed(2) }}</strong> / 张</span>
                <span>本次预计 <strong>¥{{ (selectedModel.price * outputCount).toFixed(2) }}</strong></span>
              </div>
              <p class="price-note">价格按单张参考价估算，实际费用以 API 账单为准</p>
            </div>
          </section>
          <div class="flex gap-2 items-center mt-3">
            <div class="output-count" aria-label="生成数量">
              <button v-for="n in [1, 2, 4]" :key="n" type="button" :class="{ active: outputCount === n }"
                :aria-pressed="outputCount === n" @click="outputCount = n">{{ n }} 张</button>
            </div>
            <button type="button" class="dk-btn-primary flex-1 min-w-0 py-2.5 text-[13px]" :disabled="!canSubmit" @click="submitEdit">
              {{ loading ? '生成中 · ' + elapsedSeconds + 's' : '生成编辑结果' }}
            </button>
          </div>
        </section>
      </fieldset>

      <section class="workspace-pane" aria-label="编辑工作区">
        <header class="workspace-header">
          <div class="workspace-tabs">
            <button type="button" :class="{ active: workspaceTab === 'results' }" @click="workspaceTab = 'results'">生成结果 <span v-if="chatHistory.length">{{ chatHistory.length }}</span></button>
            <button v-if="taskMode !== 'general'" type="button" :class="{ active: workspaceTab === 'canvas' }" @click="workspaceTab = 'canvas'">编辑画布</button>
          </div>
          <span class="text-[11px] text-ink-muted hidden sm:block">点击图片查看大图</span>
        </header>

        <div v-if="error" class="error-banner" role="alert">{{ error }}</div>
        <div v-if="sessionLoading" class="workspace-empty" role="status">
          <span class="status-spinner"></span>
          <h2>正在恢复历史会话</h2>
          <p>加载原图与生成结果…</p>
        </div>

        <template v-else>
          <div v-if="loading" class="generation-status" role="status" aria-live="polite">
            <span class="status-spinner"></span>
            <div class="flex-1">
              <p class="text-sm font-medium text-ink">{{ loadingHint }}</p>
              <p class="text-xs text-ink-muted mt-1">已等待 {{ elapsedSeconds }} 秒，完成后结果会显示在这里</p>
            </div>
          </div>

          <div v-show="workspaceTab === 'canvas'" class="canvas-workspace" :inert="loading">
            <template v-if="mainImagePreview && taskMode !== 'general'">
              <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
                <p class="text-xs text-ink-muted">当前画布：<span class="font-medium text-ink">{{ sourceLabel }}</span></p>
                <button type="button" class="text-xs text-brand" @click="viewImage(editingImagePreview, sourceLabel)">放大查看底图 ↗</button>
              </div>
              <ImageCanvasEditor :key="editingImagePreview" ref="canvasEditor"
                :image-src="editingImagePreview" :task-mode="taskMode" :text-layers="textLayers"
                @update:text-layers="textLayers = $event" :brush-size="brushSize" :mask-tool="maskTool"
                :mask-feather="maskFeather" :text-tool="textTool" :mask-src="maskPreviewUrl" :disabled="loading" />
            <div v-if="mainImagePreview && taskMode === 'local_edit'" class="mt-3 rounded-xl border border-line bg-white p-3">
              <div class="flex flex-col gap-2 mb-2 sm:flex-row sm:items-center sm:justify-between">
                <span class="text-[12px] font-medium text-ink-soft">涂抹需要修改的区域</span>
                <div class="flex flex-wrap items-center gap-1">
                  <button
                    type="button"
                    class="dk-btn-ghost text-[12px]"
                    :class="maskTool === 'paint' ? 'bg-selected text-ink' : ''"
                    @click="maskTool = 'paint'"
                  >
                    画笔
                  </button>
                  <button
                    type="button"
                    class="dk-btn-ghost text-[12px]"
                    :class="maskTool === 'erase' ? 'bg-selected text-ink' : ''"
                    @click="maskTool = 'erase'"
                  >
                    橡皮
                  </button>
                  <button type="button" class="dk-btn-ghost text-[12px]" @click="canvasEditor?.undoMask()">撤销</button>
                  <button type="button" class="dk-btn-ghost text-[12px]" @click="maskPreviewUrl = ''; canvasEditor?.clearMask()">清空</button>
                </div>
              </div>
              <div class="space-y-2">
                <label class="flex items-center gap-3 text-[12px] text-ink-muted">
                  大小
                  <input v-model.number="brushSize" type="range" min="12" max="140" class="flex-1" />
                  <span class="w-8 text-right">{{ brushSize }}</span>
                </label>
                <label class="flex items-center gap-3 text-[12px] text-ink-muted">
                  羽化
                  <input v-model.number="maskFeather" type="range" min="0" max="24" class="flex-1" />
                  <span class="w-8 text-right">{{ maskFeather }}</span>
                </label>
              </div>
            </div>

            <div v-if="mainImagePreview && taskMode === 'text_layer'" class="mt-3 rounded-xl border border-line bg-white p-3">
              <div class="flex flex-col gap-2 mb-2 sm:flex-row sm:items-center sm:justify-between">
                <span class="text-[12px] font-medium text-ink-soft">文字编辑工具</span>
                <div class="flex flex-wrap items-center gap-1">
                  <button
                    type="button"
                    class="dk-btn-ghost text-[12px]"
                    :class="textTool === 'select' ? 'bg-selected text-ink' : ''"
                    @click="textTool = 'select'; maskTool = 'paint'"
                  >
                    拖拽缩放
                  </button>
                  <button
                    type="button"
                    class="dk-btn-ghost text-[12px]"
                    :class="textTool === 'erase' ? 'bg-selected text-ink' : ''"
                    @click="textTool = 'erase'; maskTool = 'paint'"
                  >
                    擦除原文字
                  </button>
                  <button type="button" class="dk-btn-ghost text-[12px]" @click="canvasEditor?.undoMask()">撤销</button>
                  <button type="button" class="dk-btn-ghost text-[12px]" @click="maskPreviewUrl = ''; canvasEditor?.clearMask()">清空</button>
                </div>
              </div>
              <div v-if="textTool === 'erase'" class="space-y-2">
                <label class="flex items-center gap-3 text-[12px] text-ink-muted">
                  擦除大小
                  <input v-model.number="brushSize" type="range" min="12" max="140" class="flex-1" />
                  <span class="w-8 text-right">{{ brushSize }}</span>
                </label>
                <p class="text-[11px] text-ink-faint">先涂抹原文字区域，再切回拖拽缩放调整新文字。</p>
              </div>
              <p v-else class="text-[11px] text-ink-faint">点击文字可选中并拖动，拖动蓝色方块可缩放字号。</p>
            </div>


            </template>
            <div v-else class="workspace-empty"><h2>先上传一张原图</h2><p>上传后可在画布上涂抹区域或调整文字</p></div>
          </div>

          <div v-if="workspaceTab === 'results'">
            <article v-if="selectedRecord" class="result-article">
              <div class="result-heading">
                <div class="min-w-0">
                  <div class="flex items-center gap-2 mb-2">
                    <span class="round-label">第 {{ selectedRound }} 轮</span>
                    <span class="text-[11px] text-ink-muted">{{ selectedRecord.result_urls?.length || 0 }} 张结果</span>
                  </div>
                  <h2 class="text-sm font-medium leading-6 text-ink break-words">{{ selectedRecord.instruction }}</h2>
                </div>
                <span v-if="selectedRecord.duration_ms" class="text-xs text-ink-muted shrink-0">{{ (selectedRecord.duration_ms / 1000).toFixed(1) }}s</span>
              </div>

              <div class="result-grid" :class="{ multiple: (selectedRecord.result_urls?.length || 0) > 1 }">
                <figure v-for="(url, imgIndex) in selectedRecord.result_urls" :key="url" class="result-tile">
                  <button type="button" class="result-preview preview-surface" :aria-label="`放大查看第 ${selectedRound} 轮结果 ${imgIndex + 1}`"
                    @click="viewImage(url, `第 ${selectedRound} 轮 · 结果 ${imgIndex + 1}`)">
                    <img :src="url" :alt="`第 ${selectedRound} 轮结果 ${imgIndex + 1}`" />
                    <span class="zoom-hint">点击放大 ↗</span>
                  </button>
                  <figcaption class="result-actions">
                    <span class="text-xs text-ink-muted">结果 {{ imgIndex + 1 }}</span>
                    <div class="flex gap-3 items-center">
                      <button type="button" class="text-xs text-ink-soft hover:text-brand" @click="downloadImage(url)">下载</button>
                      <button type="button" class="continue-button" :disabled="loading" @click="continueFromRecord(selectedRecord, imgIndex)">
                        {{ currentParentId === selectedRecord.id && currentParentResultIndex === imgIndex ? '已用作编辑底图' : '基于此图编辑' }}
                      </button>
                    </div>
                  </figcaption>
                </figure>
              </div>
              <footer class="result-footer">
                <span>{{ selectedRecord.model || selectedRecord.provider }}<template v-if="selectedRecord.edit_metadata?.model_selection?.resolution"> · {{ selectedRecord.edit_metadata.model_selection.resolution.toUpperCase() }}</template></span>
                <span v-if="selectedRecord.cost_currency === 'CNY' && selectedRecord.cost !== undefined">
                  {{ selectedRecord.edit_metadata?.model_selection?.price_per_image !== undefined
                    ? `¥${selectedRecord.edit_metadata.model_selection.price_per_image.toFixed(2)} / 张`
                    : '' }}
                  本次费用 ¥{{ selectedRecord.cost.toFixed(2) }}
                </span>
                <span v-if="selectedRecord.fallback_used">已切换备用模型</span>
              </footer>
            </article>
            <div v-else-if="!loading" class="workspace-empty">
              <div class="empty-art" aria-hidden="true">
                <svg width="38" height="38" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
                  <rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m3 17 5-5 4 4 4-6 5 7"/>
                </svg>
              </div>
              <h2>下一张好图，从这里开始</h2>
              <p>上传原图，描述修改，结果将在这里呈现。</p>
              <div class="empty-steps"><span>01 上传图片</span><i>→</i><span>02 描述修改</span><i>→</i><span>03 查看结果</span></div>
            </div>
          </div>

          <div v-if="chatHistory.length" class="history-panel">
            <div class="section-heading"><h3>编辑记录</h3><span>切换查看 · 保留所有轮次</span></div>
            <div class="history-strip" aria-label="编辑轮次">
              <button v-for="(record, index) in chatHistory" :key="record.id" type="button"
                class="history-item" :class="{ active: selectedRecordId === record.id }"
                :aria-pressed="selectedRecordId === record.id" :title="record.instruction"
                @click="selectedRecordId = record.id; workspaceTab = 'results'">
                <img v-if="record.result_urls?.[0]" :src="record.result_urls[0]" :alt="`第 ${index + 1} 轮缩略图`" />
                <div class="min-w-0"><span class="block text-xs font-medium">第 {{ index + 1 }} 轮</span><span class="block truncate text-[11px] text-ink-muted mt-1">{{ record.instruction }}</span></div>
              </button>
            </div>
          </div>
        </template>
      </section>
    </div>
    <ImageLightbox v-if="lightbox" :src="lightbox.url" :title="lightbox.title" @close="lightbox = null" />
  </div>
</template>

<style scoped>
.editor-page { max-width: 1440px; margin: auto; padding: 24px 28px 36px; }
.editor-header { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 22px; }
.editor-layout { display: grid; grid-template-columns: 336px minmax(0, 1fr); gap: 22px; align-items: start; }
.control-pane { min-width: 0; margin: 0; padding: 18px; background: white; border: 1px solid #e5e8ef; border-radius: 16px; }
.control-pane:disabled { opacity: .7; }
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 10px; }
.section-heading h2, .section-heading h3 { font-size: 13px; font-weight: 600; color: #25334b; }
.section-heading span { font-size: 10px; color: #8992a3; }
.original-drop { display: flex; align-items: center; gap: 12px; padding: 10px; border: 1px dashed #dce1ea; border-radius: 10px; }
.dragging { border-color: #258cff !important; background: #eef7ff !important; }
.original-preview { position: relative; flex: 0 0 96px; width: 96px; height: 116px; border-radius: 6px; }
.preview-surface { background: #f0f2f6; overflow: hidden; cursor: zoom-in; }
.preview-surface img { display: block; width: 100%; height: 100%; object-fit: contain; }
.zoom-hint { position: absolute; bottom: 8px; right: 8px; padding: 4px 7px; border-radius: 5px; color: #475569; background: #ffffffed; font-size: 10px; box-shadow: 0 1px 5px #0f172a12; }
.upload-placeholder { min-height: 136px; width: 100%; display: flex; flex-direction: column; justify-content: center; align-items: center; }
.reference-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; border-radius: 8px; }
.reference-tile { position: relative; min-width: 0; height: 70px; }
.reference-preview { width: 100%; height: 100%; border: 1px solid #e5e8ef; border-radius: 8px; }
.remove-reference { position: absolute; top: -5px; right: -5px; width: 20px; height: 20px; background: white; border: 1px solid #dce1ea; border-radius: 50%; color: #64748b; font-size: 14px; line-height: 1; }
.reference-add { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; height: 70px; border: 1px dashed #dce1ea; border-radius: 8px; color: #8390a4; cursor: pointer; font-size: 10px; }
.reference-add:hover, .reference-add:focus-within { color: #258cff; border-color: #258cff; }
.control-pane :deep(.dk-card) { padding: 16px 0; margin-top: 16px; border-top: 1px solid #edf0f4; background: transparent; border-radius: 0; }
.control-pane :deep(.dk-section-title) { font-size: 13px; }
.control-pane :deep(.dk-card .text-\[12px\].text-ink-faint) { display: none; }
.control-pane :deep(.dk-card button) { padding: 10px 6px; }
.control-pane :deep(.dk-card button .text-\[11px\]) { display: none; }
.instruction-panel { padding-top: 16px; border-top: 1px solid #edf0f4; }
.instruction-panel textarea { border-radius: 10px; padding: 12px; line-height: 1.7; }
.advanced-settings { margin-top: 12px; border: 1px solid #e7eaf0; border-radius: 9px; overflow: hidden; background: #fff; }
.advanced-toggle { display: flex; width: 100%; min-height: 42px; align-items: center; justify-content: space-between; gap: 10px; padding: 10px; color: #526176; font-size: 11px; text-align: left; }
.advanced-toggle > span:last-child { min-width: 0; display: flex; align-items: center; gap: 7px; color: #8590a0; }
.advanced-toggle > span:last-child > span:first-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.advanced-chevron { transition: transform .16s ease; }
.advanced-chevron.open { transform: rotate(180deg); }
.advanced-content { padding: 0 10px 11px; border-top: 1px solid #edf0f4; }
.setting-label { display: block; margin: 10px 0 6px; color: #657286; font-size: 10px; font-weight: 600; }
.setting-select { width: 100%; min-width: 0; padding: 9px 10px; border: 1px solid #dfe4ec; border-radius: 7px; color: #2d3b50; background: white; font-size: 11px; }
.model-detail { display: flex; justify-content: space-between; gap: 8px; color: #929bab; font-size: 9px; margin-top: 6px; overflow-wrap: anywhere; }
.resolution-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-top: 6px; }
.resolution-row .setting-label { margin-bottom: 0; }
.resolution-select { min-width: 96px; padding: 6px 8px; border: 1px solid #dfe4ec; border-radius: 6px; font-size: 10px; background: white; }
.fixed-resolution { color: #48576b; font-size: 10px; }
.price-summary { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; margin-top: 11px; padding: 9px; border-radius: 7px; color: #657286; background: #f5f7fa; font-size: 10px; }
.price-summary strong { color: #293950; font-size: 12px; }
.price-note { margin-top: 7px; color: #9aa2af; font-size: 9px; line-height: 1.5; }
.submission-source { display: flex; gap: 8px; align-items: center; margin-top: 10px; padding: 8px; background: #f6f8fb; border-radius: 8px; }
.submission-source img { width: 30px; height: 34px; object-fit: contain; border-radius: 4px; background: #e9edf4; }
.output-count { display: flex; padding: 3px; border: 1px solid #e5e8ef; border-radius: 8px; white-space: nowrap; }
.output-count button { padding: 6px; border-radius: 5px; font-size: 11px; color: #7c8799; }
.output-count button.active { background: #eaf4ff; color: #1683ee; }
.workspace-pane { min-width: 0; border: 1px solid #e5e8ef; background: white; border-radius: 16px; overflow: hidden; }
.workspace-header { display: flex; align-items: center; justify-content: space-between; padding: 0 20px; border-bottom: 1px solid #edf0f4; gap: 10px; }
.workspace-tabs { display: flex; gap: 20px; }
.workspace-tabs button { padding: 17px 0 15px; border-bottom: 2px solid transparent; font-size: 13px; color: #8a93a3; }
.workspace-tabs button.active { color: #263650; border-color: #258cff; font-weight: 600; }
.workspace-tabs span { padding: 2px 6px; background: #f0f3f8; border-radius: 5px; font-size: 10px; margin-left: 4px; }
.result-article, .canvas-workspace { padding: 20px; }
.result-heading { display: flex; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.round-label { color: #2584dd; background: #eef6ff; font-size: 10px; font-weight: 600; padding: 3px 8px; border-radius: 5px; }
.result-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 14px; }
.result-grid.multiple { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.result-tile { min-width: 0; border: 1px solid #e5e8ef; border-radius: 10px; overflow: hidden; }
.result-preview { display: block; position: relative; width: 100%; height: clamp(220px, 36vh, 320px); padding: 12px; }
.result-grid.multiple .result-preview { height: clamp(160px, 24vh, 220px); }
.result-actions { padding: 10px 12px; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; }
.continue-button { border: 1px solid #d9e8fa; border-radius: 6px; font-size: 11px; padding: 5px 8px; color: #2877cd; background: #f5faff; }
.continue-button:disabled { opacity: .5; cursor: not-allowed; }
.result-footer { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 14px; font-size: 10px; color: #9099a8; overflow-wrap: anywhere; }
.history-panel { border-top: 1px solid #edf0f4; padding: 16px 20px; }
.history-strip { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 4px; }
.history-item { flex: 0 0 160px; min-width: 0; display: flex; align-items: center; text-align: left; gap: 8px; padding: 7px; border: 1px solid #e5e8ef; border-radius: 8px; color: #475569; }
.history-item.active { border-color: #87bfff; background: #f3f9ff; }
.history-item img { width: 38px; height: 44px; object-fit: contain; border-radius: 4px; background: #edf0f4; flex-shrink: 0; }
.workspace-empty { min-height: 430px; padding: 40px 24px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }
.workspace-empty h2 { font-size: 16px; color: #334155; font-weight: 600; }
.workspace-empty p { font-size: 12px; color: #939cab; margin-top: 10px; line-height: 1.7; }
.empty-art { width: 78px; height: 78px; display: grid; place-items: center; border: 1px solid #e1e8f1; background: #f8fafc; color: #8eaac7; border-radius: 22px; margin-bottom: 24px; transform: rotate(-6deg); }
.empty-steps { display: flex; flex-wrap: wrap; justify-content: center; gap: 12px; font-size: 10px; color: #99a3b2; margin-top: 32px; }
.empty-steps i { font-style: normal; color: #c1c9d5; }
.generation-status { display: flex; align-items: center; gap: 14px; margin: 16px 20px 0; padding: 16px; background: #f4f9ff; border: 1px solid #e0edfd; border-radius: 10px; }
.status-spinner { display: block; width: 22px; height: 22px; flex-shrink: 0; border: 2px solid #d9e8fb; border-top-color: #258cff; border-radius: 50%; animation: spin 1s linear infinite; }
.workspace-empty .status-spinner { margin-bottom: 20px; }
.error-banner { margin: 16px 20px; padding: 12px; background: #fff6f5; border: 1px solid #f5d8d6; border-radius: 8px; font-size: 12px; color: #c34842; overflow-wrap: anywhere; }
button:focus-visible, label:focus-within { outline: 2px solid #258cff; outline-offset: 3px; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (min-width: 1200px) { .control-pane { position: sticky; top: 20px; } }
@media (max-width: 1100px) { .editor-page { padding: 20px; } .editor-layout { grid-template-columns: 300px minmax(0, 1fr); gap: 16px; } .control-pane { padding: 14px; } .original-preview { flex-basis: 82px; width: 82px; height: 100px; } .result-grid.multiple { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 767px) { .editor-page { padding: 16px; } .editor-header { margin-bottom: 16px; } .editor-header h1 { font-size: 16px; } .editor-layout { grid-template-columns: minmax(0, 1fr); } .reference-grid { grid-template-columns: repeat(auto-fill, minmax(60px, 1fr)); } .original-preview { flex-basis: 88px; width: 88px; height: 100px; } .workspace-header { padding: 0 16px; } .result-article, .canvas-workspace { padding: 16px; } .history-panel { padding: 14px 16px; } .result-preview { height: 280px; } .workspace-empty { min-height: 300px; } }
@media (prefers-reduced-motion: reduce) { .status-spinner { animation: none; } }
</style>
