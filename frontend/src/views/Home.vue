<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { editImage, getProviders, getSession } from '@/api'
import ImageCanvasEditor from '@/components/ImageCanvasEditor.vue'
import TaskModePanel from '@/components/TaskModePanel.vue'
import TextLayerPanel from '@/components/TextLayerPanel.vue'
import type { EditMetadata, ProviderInfo, EditRecord, TaskMode, TextLayer } from '@/types'

const route = useRoute()
const router = useRouter()

// 状态
const mainImage = ref<File | null>(null)
const mainImagePreview = ref<string>('')
const referenceImages = ref<File[]>([])
const referenceImagePreviews = ref<string[]>([])
const instruction = ref('')
const selectedProvider = ref<string>('')
const outputCount = ref(1)
const taskMode = ref<TaskMode>('general')
const textLayers = ref<TextLayer[]>([])
const brushSize = ref(48)
const maskPreviewUrl = ref('')
const canvasEditor = ref<InstanceType<typeof ImageCanvasEditor> | null>(null)

// 会话状态
const sessionId = ref<string>('')
const chatHistory = ref<EditRecord[]>([])
const currentParentId = ref<number | null>(null)
const currentParentResultIndex = ref(0)

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

// Providers
const providers = ref<ProviderInfo[]>([])
const defaultProvider = ref('gemini')

// 模型卡片元数据：标语 + 描述（用于卡片选择器）
const providerMeta: Record<string, { tagline: string; desc: string; emoji: string }> = {
  gemini: { tagline: '多图 · 多轮', desc: '参考图替换、迭代编辑首选', emoji: '✦' },
  openai: { tagline: '文字最强', desc: '海报、广告牌文字渲染', emoji: 'A' },
  seededit: { tagline: '中文场景', desc: '中文海报、电商图优化', emoji: '中' },
  tongyi: { tagline: '通义万相', desc: '阿里图像编辑', emoji: '万' },
  flux: { tagline: '高保真', desc: 'FLUX Kontext 高质量', emoji: '⚡' }
}

// 拖拽状态
const isDragging = ref(false)

// 计算属性
const canSubmit = computed(() => {
  const hasInstruction = instruction.value.trim().length > 0
  const hasTextLayer = taskMode.value === 'text_layer' && textLayers.value.length > 0
  return mainImage.value && (hasInstruction || hasTextLayer) && !loading.value && !sessionLoading.value
})

// 加载 providers
onMounted(async () => {
  try {
    const data = await getProviders()
    providers.value = data.providers.filter(p => p.enabled)
    defaultProvider.value = data.default
  } catch (e) {
    console.error('加载 providers 失败:', e)
  }
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
    referenceImages.value = []
    referenceImagePreviews.value = []
    instruction.value = ''
    chatHistory.value = data.records

    const lastRecord = data.records[data.records.length - 1]
    const metadata = lastRecord?.edit_metadata
    taskMode.value = metadata?.task_mode || 'general'
    textLayers.value = metadata?.text_layers || []
    brushSize.value = metadata?.mask?.brushSize || 48
    maskPreviewUrl.value = lastRecord?.mask_url || ''
    currentParentId.value = lastRecord?.id ?? null
    currentParentResultIndex.value = 0
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
}

function setMainImage(file: File) {
  sessionLoadToken++
  mainImage.value = file
  const reader = new FileReader()
  reader.onload = (e) => {
    mainImagePreview.value = e.target?.result as string
  }
  reader.readAsDataURL(file)
  sessionId.value = ''
  chatHistory.value = []
  currentParentId.value = null
  currentParentResultIndex.value = 0
  taskMode.value = 'general'
  textLayers.value = []
  maskPreviewUrl.value = ''
  void canvasEditor.value?.clearMask()
  if (route.query.sessionId) {
    void router.replace({ path: '/' })
  }
}

// 处理参考图上传
function handleReferenceImageChange(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files) {
    Array.from(input.files).forEach(file => {
      referenceImages.value.push(file)
      const reader = new FileReader()
      reader.onload = (e) => {
        referenceImagePreviews.value.push(e.target?.result as string)
      }
      reader.readAsDataURL(file)
    })
  }
}

function removeReferenceImage(index: number) {
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
  if (files && files[0]) {
    setMainImage(files[0])
  }
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
      mask: { brushSize: brushSize.value }
    }
    const mainImageForSubmit = taskMode.value === 'text_layer' && canvasEditor.value
      ? await canvasEditor.value.exportCompositeImage()
      : mainImage.value!
    const maskImage = taskMode.value === 'local_edit' && canvasEditor.value
      ? await canvasEditor.value.exportMaskImage()
      : null
    const instructionText = instruction.value.trim() || '修改文字图层'

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
        provider: selectedProvider.value || undefined,
        outputCount: outputCount.value,
        referenceImages: referenceImages.value.length > 0 ? referenceImages.value : undefined
      }
    )

    sessionId.value = result.session_id
    currentParentId.value = result.record_id
    currentParentResultIndex.value = 0

    chatHistory.value.push({
      id: result.record_id,
      session_id: result.session_id,
      main_image_url: mainImagePreview.value,
      instruction: instructionText,
      task_type: result.task_type,
      provider: result.provider,
      model: result.model,
      fallback_used: result.fallback_used,
      result_urls: result.results,
      mask_url: maskImage ? URL.createObjectURL(maskImage) : undefined,
      edit_metadata: metadata,
      status: 'completed',
      cost: result.cost,
      duration_ms: result.duration_ms,
      created_at: new Date().toISOString()
    })

    instruction.value = ''
    if (result.results[0]) {
      try {
        mainImage.value = await fileFromUrl(result.results[0], 'latest_result.png')
        mainImagePreview.value = result.results[0]
      } catch {
        mainImage.value = mainImageForSubmit
      }
    }
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
async function continueFromRecord(record: EditRecord, resultIndex: number = 0) {
  currentParentId.value = record.id
  currentParentResultIndex.value = resultIndex
  const selectedUrl = record.result_urls?.[resultIndex]
  if (selectedUrl) {
    try {
      mainImage.value = await fileFromUrl(selectedUrl, 'selected_result.png')
      mainImagePreview.value = selectedUrl
      textLayers.value = record.edit_metadata?.text_layers || []
      taskMode.value = record.edit_metadata?.task_mode || taskMode.value
      brushSize.value = record.edit_metadata?.mask?.brushSize || brushSize.value
      maskPreviewUrl.value = record.mask_url || ''
    } catch (e) {
      error.value = '加载选中的结果图失败'
    }
  }
  const index = chatHistory.value.findIndex(r => r.id === record.id)
  if (index >= 0) {
    chatHistory.value = chatHistory.value.slice(0, index + 1)
  }
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
  sessionLoadToken++
  mainImage.value = null
  mainImagePreview.value = ''
  referenceImages.value = []
  referenceImagePreviews.value = []
  instruction.value = ''
  sessionId.value = ''
  chatHistory.value = []
  currentParentId.value = null
  currentParentResultIndex.value = 0
  taskMode.value = 'general'
  textLayers.value = []
  brushSize.value = 48
  maskPreviewUrl.value = ''
  error.value = ''
  if (route.query.sessionId) {
    void router.replace({ path: '/' })
  }
}

// 示例指令
const examples = ['去掉水印', '替换背景', '修改文字颜色', '移除某个物体']
</script>

<template>
  <div class="min-h-screen">
    <!-- 顶部 bar -->
    <header class="sticky top-0 z-10 bg-canvas/80 backdrop-blur border-b border-line/60">
      <div class="max-w-[1400px] mx-auto px-8 py-4 flex items-center gap-6">
        <h1 class="text-[18px] font-semibold text-ink shrink-0">AI 图像编辑</h1>
        <div class="flex-1 max-w-2xl">
          <div class="dk-input flex items-center gap-2 cursor-text">
            <svg class="w-4 h-4 text-ink-faint" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="m21 21-4.3-4.3M11 18a7 7 0 1 1 0-14 7 7 0 0 1 0 14Z"/>
            </svg>
            <span class="text-ink-faint">输入想要的修改，或试试热门指令 →</span>
            <div class="ml-auto flex gap-2">
              <button
                v-for="ex in examples.slice(0, 3)"
                :key="ex"
                class="text-[12px] text-ink-muted hover:text-brand"
                @click="instruction = ex"
              >
                {{ ex }}
              </button>
            </div>
          </div>
        </div>
        <div class="ml-auto text-[12px] text-ink-muted">
          基于原图精准修改，其他部分保持不变
        </div>
      </div>
    </header>

    <div class="max-w-[1400px] mx-auto px-8 py-6">
      <div class="grid grid-cols-12 gap-6">

        <!-- 左侧：上传与控制（5 列） -->
        <div class="col-span-12 lg:col-span-5 space-y-4">

          <!-- 图片卡：主图 + 参考图（合并） -->
          <section class="dk-card p-5">
            <div class="flex items-center justify-between mb-3">
              <h2 class="dk-section-title">图片</h2>
              <span class="text-[12px] text-ink-faint">JPG / PNG / WebP，≤ 20MB</span>
            </div>

            <!-- 主图区 -->
            <div
              v-if="!mainImagePreview"
              class="rounded-card bg-white border border-dashed transition-colors cursor-pointer aspect-[16/10] flex flex-col items-center justify-center"
              :class="isDragging ? 'border-brand bg-brand-50' : 'border-line hover:border-brand/60'"
              @dragover="handleDragOver"
              @dragleave="handleDragLeave"
              @drop="handleDrop"
              @click="($refs.mainImageInput as HTMLInputElement).click()"
            >
              <svg class="w-10 h-10 text-ink-faint mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 7.5m0 0L7.5 12M12 7.5v13"/>
              </svg>
              <p class="text-ink-soft font-medium text-[14px]">拖拽图片到此处，或点击上传</p>
              <p class="text-ink-faint text-[12px] mt-1">上传后开始基于原图的精准编辑</p>
              <input
                ref="mainImageInput"
                type="file"
                accept="image/*"
                class="hidden"
                @change="handleMainImageChange"
              />
            </div>

            <div v-else class="relative rounded-card overflow-hidden bg-white">
              <ImageCanvasEditor
                ref="canvasEditor"
                :image-src="mainImagePreview"
                :task-mode="taskMode"
                :text-layers="textLayers"
                :brush-size="brushSize"
                :mask-src="maskPreviewUrl"
              />
              <button
                class="absolute top-3 right-3 bg-white/90 backdrop-blur w-7 h-7 rounded-full flex items-center justify-center text-ink-soft hover:text-ink shadow-sm"
                @click="reset"
                title="重新上传"
              >
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.4">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12"/>
                </svg>
              </button>
            </div>

            <div v-if="mainImagePreview && taskMode === 'local_edit'" class="mt-3 rounded-xl border border-line bg-white p-3">
              <div class="flex items-center justify-between gap-3 mb-2">
                <span class="text-[12px] font-medium text-ink-soft">涂抹需要修改的区域</span>
                <div class="flex items-center gap-1">
                  <button type="button" class="dk-btn-ghost text-[12px]" @click="canvasEditor?.undoMask()">撤销</button>
                  <button type="button" class="dk-btn-ghost text-[12px]" @click="maskPreviewUrl = ''; canvasEditor?.clearMask()">清空</button>
                </div>
              </div>
              <label class="flex items-center gap-3 text-[12px] text-ink-muted">
                画笔
                <input v-model.number="brushSize" type="range" min="12" max="140" class="flex-1" />
                <span class="w-8 text-right">{{ brushSize }}</span>
              </label>
            </div>

            <!-- 参考图缩略图条（内联在主图卡内） -->
            <div class="mt-3 pt-3 border-t border-line/60">
              <div class="flex items-center justify-between mb-2">
                <span class="text-[12px] font-medium text-ink-soft">参考图</span>
                <span class="text-[11px] text-ink-faint">可选 · 用于风格/物件参考</span>
              </div>
              <div class="flex flex-wrap gap-2">
                <div
                  v-for="(preview, index) in referenceImagePreviews"
                  :key="index"
                  class="relative w-14 h-14 rounded-lg overflow-hidden bg-white border border-line"
                >
                  <img :src="preview" class="w-full h-full object-cover" />
                  <button
                    class="absolute top-0.5 right-0.5 bg-white/95 w-4 h-4 rounded-full flex items-center justify-center text-ink-soft hover:text-ink shadow-sm"
                    @click="removeReferenceImage(index)"
                  >
                    <svg class="w-2 h-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="3">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12"/>
                    </svg>
                  </button>
                </div>

                <label
                  class="w-14 h-14 rounded-lg border border-dashed border-line bg-white flex items-center justify-center cursor-pointer hover:border-brand/60 text-ink-faint hover:text-brand transition-colors"
                  title="添加参考图"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.6">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15"/>
                  </svg>
                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    class="hidden"
                    @change="handleReferenceImageChange"
                  />
                </label>
              </div>
            </div>
          </section>

          <TaskModePanel v-model="taskMode" />

          <TextLayerPanel
            v-if="taskMode === 'text_layer'"
            v-model="textLayers"
          />

          <!-- 模型卡：卡片式选择器 -->
          <section v-if="taskMode !== 'text_layer'" class="dk-card p-5">
            <div class="flex items-center justify-between mb-3">
              <h2 class="dk-section-title">选择模型</h2>
              <span class="text-[12px] text-ink-faint">不同模型擅长不同任务</span>
            </div>

            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              <!-- 自动卡 -->
              <button
                type="button"
                class="relative text-left rounded-xl border p-3 transition-all"
                :class="selectedProvider === ''
                  ? 'border-brand bg-brand-50/60 shadow-sm'
                  : 'border-line bg-white hover:border-brand/40 hover:bg-brand-50/30'"
                @click="selectedProvider = ''"
              >
                <div class="flex items-center gap-1.5 mb-2">
                  <div
                    class="w-7 h-7 rounded-lg flex items-center justify-center text-[14px]"
                    :class="selectedProvider === '' ? 'bg-brand text-white' : 'bg-canvas text-ink-soft'"
                  >
                    ✨
                  </div>
                  <span
                    v-if="selectedProvider === ''"
                    class="ml-auto w-2 h-2 rounded-full bg-brand"
                  ></span>
                </div>
                <div class="text-[13px] font-semibold text-ink leading-tight">自动</div>
                <div class="text-[11px] text-ink-muted mt-0.5">根据指令智能选择</div>
                <div class="text-[10px] text-brand mt-1.5 font-medium">推荐</div>
              </button>

              <!-- 各模型卡 -->
              <button
                v-for="p in providers"
                :key="p.name"
                type="button"
                class="relative text-left rounded-xl border p-3 transition-all"
                :class="selectedProvider === p.name
                  ? 'border-brand bg-brand-50/60 shadow-sm'
                  : 'border-line bg-white hover:border-brand/40 hover:bg-brand-50/30'"
                @click="selectedProvider = p.name"
                :title="p.model"
              >
                <div class="flex items-center gap-1.5 mb-2">
                  <div
                    class="w-7 h-7 rounded-lg flex items-center justify-center text-[12px] font-bold"
                    :class="selectedProvider === p.name ? 'bg-brand text-white' : 'bg-canvas text-ink-soft'"
                  >
                    {{ providerMeta[p.name]?.emoji || p.name[0].toUpperCase() }}
                  </div>
                  <span
                    v-if="selectedProvider === p.name"
                    class="ml-auto w-2 h-2 rounded-full bg-brand"
                  ></span>
                </div>
                <div class="text-[13px] font-semibold text-ink leading-tight truncate">{{ p.display_name }}</div>
                <div class="text-[11px] text-ink-muted mt-0.5 truncate">
                  {{ providerMeta[p.name]?.tagline || p.model }}
                </div>
                <div class="text-[10px] text-ink-faint mt-1.5 line-clamp-1">
                  {{ providerMeta[p.name]?.desc || '通用图像编辑' }}
                </div>
              </button>
            </div>
          </section>

          <!-- 指令卡 -->
          <section class="dk-card p-5">
            <div class="flex items-center justify-between mb-3">
              <h2 class="dk-section-title">编辑指令</h2>
              <span class="text-[12px] text-ink-faint">Ctrl + Enter 提交</span>
            </div>

            <textarea
              v-model="instruction"
              placeholder="描述你想要的修改，例如：把椅子换成参考图中的款式 / 去掉右下角水印 / 把广告牌上的 SALE 改成 NEW"
              class="dk-textarea"
              rows="4"
              @keydown.ctrl.enter="submitEdit"
            />

            <div
              v-if="currentParentId"
              class="mt-3 flex items-center justify-between gap-3 rounded-lg border border-brand/20 bg-brand-50 px-3 py-2 text-[12px]"
            >
              <span class="text-ink-soft">
                基于记录 #{{ currentParentId }} 的第 {{ currentParentResultIndex + 1 }} 张继续
              </span>
              <button
                class="text-brand font-medium hover:underline"
                @click="currentParentId = null; currentParentResultIndex = 0"
              >
                改回原图
              </button>
            </div>

            <!-- 示例指令 -->
            <div class="mt-3 flex flex-wrap gap-2">
              <button
                v-for="ex in examples"
                :key="ex"
                class="text-[12px] px-2.5 py-1 rounded-full bg-white border border-line text-ink-muted hover:text-brand hover:border-brand/40 transition-colors"
                @click="instruction = ex"
              >
                {{ ex }}
              </button>
            </div>

            <!-- 提交栏：生成数量 + 提交按钮内联 -->
            <div class="mt-4 flex items-center gap-3">
              <div
                v-if="taskMode !== 'text_layer'"
                class="flex items-center gap-1 bg-white border border-line rounded-lg p-0.5"
              >
                <button
                  v-for="n in [1, 2, 4]"
                  :key="n"
                  class="px-2.5 py-1 text-[12px] rounded-md transition-colors"
                  :class="outputCount === n
                    ? 'bg-brand text-white font-medium'
                    : 'text-ink-muted hover:text-ink'"
                  @click="outputCount = n"
                >
                  {{ n }} 张
                </button>
              </div>

              <button
                class="flex-1 py-3 rounded-card font-medium text-white text-[14px] transition-all"
                :class="canSubmit
                  ? 'bg-brand hover:bg-brand/90 shadow-sm hover:shadow-hover'
                  : 'bg-ink-faint/40 cursor-not-allowed'"
                :disabled="!canSubmit"
                @click="submitEdit"
              >
                <span v-if="loading" class="flex items-center justify-center gap-2">
                  <svg class="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                  生成中 · {{ elapsedSeconds }}s
                </span>
                <span v-else>{{ taskMode === 'text_layer' ? '保存文字结果' : '生成编辑结果' }}</span>
              </button>
            </div>

            <div v-if="error" class="mt-3 px-3 py-2 bg-white border border-red-200 rounded-lg text-red-500 text-[13px]">
              {{ error }}
            </div>
          </section>
        </div>

        <!-- 右侧：对话历史与结果（7 列） -->
        <div class="col-span-12 lg:col-span-7 space-y-4">

          <!-- 空态 -->
          <div v-if="sessionLoading" class="dk-card p-10 text-center">
            <svg class="animate-spin h-8 w-8 text-brand mx-auto mb-4" viewBox="0 0 24 24" fill="none">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            <p class="text-ink font-medium text-[14px] mb-1">正在加载历史会话</p>
            <p class="text-ink-muted text-[12px]">正在恢复原图、提示词和生成结果</p>
          </div>

          <div
            v-if="chatHistory.length === 0 && !loading && !sessionLoading"
            class="dk-card p-12 flex flex-col items-center justify-center text-center min-h-[480px]"
          >
            <div class="w-16 h-16 rounded-2xl bg-brand-50 flex items-center justify-center mb-4">
              <svg class="w-8 h-8 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.6">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.091ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z"/>
              </svg>
            </div>
            <p class="text-[16px] font-semibold text-ink mb-1">从一张图开始</p>
            <p class="text-[13px] text-ink-muted max-w-sm">
              上传图片并输入指令，AI 将基于原图做精准局部修改。支持参考图替换、文字修改、去水印等。
            </p>
          </div>

          <!-- 对话历史 -->
          <article
            v-for="(record, index) in chatHistory"
            :key="record.id"
            class="dk-card overflow-hidden"
          >
            <!-- 指令头 -->
            <div class="px-5 py-3 bg-white/60 border-b border-line/60">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <span class="text-[11px] text-ink-faint">第 {{ index + 1 }} 轮</span>
                  <p class="text-[14px] text-ink font-medium mt-0.5 break-words">{{ record.instruction }}</p>
                </div>
                <div class="flex items-center gap-1.5 shrink-0">
                  <span class="text-[11px] bg-brand-50 text-brand px-2 py-0.5 rounded-full">
                    {{ record.provider }}
                  </span>
                  <span v-if="record.fallback_used" class="text-[11px] bg-amber-50 text-amber-600 px-2 py-0.5 rounded-full">
                    fallback
                  </span>
                </div>
              </div>
            </div>

            <!-- 结果图 -->
            <div class="p-4">
              <div
                class="grid gap-3"
                :class="record.result_urls && record.result_urls.length > 1 ? 'grid-cols-2' : 'grid-cols-1'"
              >
                <div
                  v-for="(url, imgIndex) in record.result_urls"
                  :key="imgIndex"
                  class="relative group rounded-xl overflow-hidden bg-white"
                >
                  <img
                    :src="url"
                    class="w-full object-contain"
                    :alt="`结果图 ${imgIndex + 1}`"
                  />
                  <div class="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-all flex items-center justify-center opacity-0 group-hover:opacity-100">
                    <div class="flex flex-wrap items-center justify-center gap-2 px-3">
                      <button
                        class="bg-white text-ink px-4 py-1.5 rounded-lg text-[13px] font-medium shadow-hover hover:bg-canvas"
                        @click="continueFromRecord(record, imgIndex)"
                      >
                        继续编辑此图
                      </button>
                    <button
                      class="bg-white text-ink px-4 py-1.5 rounded-lg text-[13px] font-medium shadow-hover hover:bg-canvas"
                      @click="downloadImage(url)"
                    >
                      下载
                    </button>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 操作栏 -->
              <div class="flex items-center justify-between mt-3 pt-3 border-t border-line/60">
                <div class="text-[11px] text-ink-faint flex items-center gap-2">
                  <span v-if="record.duration_ms">{{ (record.duration_ms / 1000).toFixed(1) }}s</span>
                  <span v-if="record.cost">·</span>
                  <span v-if="record.cost">${{ record.cost.toFixed(4) }}</span>
                  <span v-if="record.task_type" class="bg-white border border-line px-2 py-0.5 rounded-full ml-1">
                    {{ record.task_type }}
                  </span>
                </div>
                <button
                  v-if="index < chatHistory.length - 1"
                  class="text-[12px] text-brand hover:underline font-medium"
                  @click="continueFromRecord(record, 0)"
                >
                  从第 1 张继续
                </button>
              </div>
            </div>
          </article>

          <!-- 加载中占位 -->
          <div v-if="loading" class="dk-card p-10 text-center">
            <svg class="animate-spin h-8 w-8 text-brand mx-auto mb-4" viewBox="0 0 24 24" fill="none">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            <p class="text-ink font-medium text-[14px] mb-1">{{ loadingHint }}</p>
            <p class="text-ink-muted text-[12px] mb-2">已等待 {{ elapsedSeconds }} 秒</p>
            <p class="text-ink-faint text-[11px]">图像生成通常需要 60 ~ 120 秒</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
