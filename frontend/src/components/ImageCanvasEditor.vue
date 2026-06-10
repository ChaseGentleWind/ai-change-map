<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import type { TaskMode, TextLayer } from '@/types'

const props = defineProps<{
  imageSrc: string
  taskMode: TaskMode
  textLayers: TextLayer[]
  brushSize: number
  maskTool: 'paint' | 'erase'
  maskFeather: number
  textTool: 'select' | 'erase'
  maskSrc?: string
}>()

const emit = defineEmits<{
  'update:textLayers': [value: TextLayer[]]
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const maskCanvas = document.createElement('canvas')
const image = new Image()
const imageReady = ref(false)
const isDrawing = ref(false)
const hasMask = ref(false)
const undoStack: ImageData[] = []
const selectedTextLayerId = ref<string | null>(null)
const textInteraction = ref<{
  mode: 'move' | 'scale'
  layerId: string
  startX: number
  startY: number
  originalX: number
  originalY: number
  originalFontSize: number
} | null>(null)

watch(
  () => props.imageSrc,
  () => {
    loadImage()
  },
  { immediate: true }
)

watch(
  () => [props.taskMode, props.textLayers, props.brushSize, props.maskTool, props.maskFeather, props.textTool],
  () => render(),
  { deep: true }
)

async function loadImage() {
  imageReady.value = false
  if (!props.imageSrc) {
    renderBlank()
    return
  }

  image.onload = async () => {
    await nextTick()
    setupCanvas()
    clearMask()
    imageReady.value = true
    if (props.maskSrc) {
      await loadMask(props.maskSrc)
    }
    render()
  }
  image.src = props.imageSrc
}

watch(
  () => props.maskSrc,
  async (maskSrc) => {
    if (!imageReady.value) return
    if (maskSrc) await loadMask(maskSrc)
    else clearMask()
    render()
  }
)

function loadMask(src: string) {
  return new Promise<void>((resolve) => {
    const maskImage = new Image()
    maskImage.onload = () => {
      const ctx = maskCanvas.getContext('2d')
      if (ctx) {
        ctx.clearRect(0, 0, maskCanvas.width, maskCanvas.height)
        ctx.drawImage(maskImage, 0, 0, maskCanvas.width, maskCanvas.height)
        hasMask.value = true
      }
      resolve()
    }
    maskImage.onerror = () => resolve()
    maskImage.src = src
  })
}

function setupCanvas() {
  const canvas = canvasRef.value
  if (!canvas || !image.naturalWidth || !image.naturalHeight) return

  const maxWidth = 760
  const width = Math.min(maxWidth, image.naturalWidth)
  const height = Math.round(width * image.naturalHeight / image.naturalWidth)

  canvas.width = width
  canvas.height = height
  maskCanvas.width = width
  maskCanvas.height = height
}

function renderBlank() {
  const canvas = canvasRef.value
  if (!canvas) return
  canvas.width = 640
  canvas.height = 400
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.clearRect(0, 0, canvas.width, canvas.height)
}

function render() {
  const canvas = canvasRef.value
  const ctx = canvas?.getContext('2d')
  if (!canvas || !ctx || !imageReady.value) return

  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height)

  if (props.taskMode === 'local_edit' && hasMask.value) {
    renderMaskOverlay(ctx)
  }

  if (props.taskMode === 'text_layer' && hasMask.value) {
    renderErasedPreview(ctx, canvas.width, canvas.height)
    renderMaskOverlay(ctx, '#fb7185')
  }

  renderTextLayers(ctx, canvas.width, canvas.height)
  renderSelectedTextBox(ctx, canvas.width, canvas.height)
}

function renderMaskOverlay(ctx: CanvasRenderingContext2D, color = '#ffffff') {
  const canvas = canvasRef.value
  if (!canvas) return

  const overlay = document.createElement('canvas')
  overlay.width = canvas.width
  overlay.height = canvas.height
  const overlayCtx = overlay.getContext('2d')
  if (!overlayCtx) return

  overlayCtx.fillStyle = color
  overlayCtx.fillRect(0, 0, overlay.width, overlay.height)
  overlayCtx.globalCompositeOperation = 'destination-in'
  overlayCtx.drawImage(maskCanvas, 0, 0)

  ctx.save()
  ctx.globalAlpha = 0.38
  ctx.drawImage(overlay, 0, 0)
  ctx.restore()
}

function renderErasedPreview(ctx: CanvasRenderingContext2D, width: number, height: number) {
  const erased = createErasedCanvas(width, height)
  if (!erased) return

  ctx.save()
  ctx.drawImage(erased, 0, 0)
  ctx.restore()
}

function createErasedCanvas(width: number, height: number) {
  if (!hasMask.value) return null

  const output = document.createElement('canvas')
  output.width = width
  output.height = height
  const outputCtx = output.getContext('2d')
  if (!outputCtx) return null

  outputCtx.drawImage(image, 0, 0, width, height)

  const blurred = document.createElement('canvas')
  blurred.width = width
  blurred.height = height
  const blurredCtx = blurred.getContext('2d')
  if (!blurredCtx) return null

  blurredCtx.filter = 'blur(18px)'
  blurredCtx.drawImage(image, -18, -18, width + 36, height + 36)
  blurredCtx.filter = 'none'
  blurredCtx.globalCompositeOperation = 'destination-in'
  blurredCtx.drawImage(maskCanvas, 0, 0, width, height)

  outputCtx.drawImage(blurred, 0, 0)
  return output
}

function renderTextLayers(ctx: CanvasRenderingContext2D, width: number, height: number) {
  for (const layer of props.textLayers) {
    if (!layer.text) continue
    const scale = width / image.naturalWidth
    ctx.save()
    ctx.font = `600 ${Math.max(8, layer.fontSize * scale)}px sans-serif`
    ctx.fillStyle = layer.color
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(layer.text, layer.x * width, layer.y * height)
    ctx.restore()
  }
}

function renderSelectedTextBox(ctx: CanvasRenderingContext2D, width: number, height: number) {
  if (props.taskMode !== 'text_layer' || props.textTool !== 'select') return
  const layer = props.textLayers.find(item => item.id === selectedTextLayerId.value)
  if (!layer) return

  const box = textLayerBox(layer, width, height)
  ctx.save()
  ctx.strokeStyle = '#2563eb'
  ctx.lineWidth = 1.5
  ctx.setLineDash([5, 4])
  ctx.strokeRect(box.x, box.y, box.width, box.height)
  ctx.setLineDash([])
  ctx.fillStyle = '#2563eb'
  ctx.fillRect(box.x + box.width - 6, box.y + box.height - 6, 12, 12)
  ctx.restore()
}

function textLayerBox(layer: TextLayer, width: number, height: number) {
  const scale = width / image.naturalWidth
  const fontSize = Math.max(8, layer.fontSize * scale)
  const textWidth = Math.max(fontSize, layer.text.length * fontSize * 0.62)
  const textHeight = fontSize * 1.25
  return {
    x: layer.x * width - textWidth / 2,
    y: layer.y * height - textHeight / 2,
    width: textWidth,
    height: textHeight
  }
}

function hitTextLayer(point: { x: number; y: number }) {
  const canvas = canvasRef.value
  if (!canvas) return null

  for (const layer of [...props.textLayers].reverse()) {
    const box = textLayerBox(layer, canvas.width, canvas.height)
    const onHandle = point.x >= box.x + box.width - 12
      && point.x <= box.x + box.width + 12
      && point.y >= box.y + box.height - 12
      && point.y <= box.y + box.height + 12

    if (onHandle) {
      return { layer, mode: 'scale' as const }
    }

    if (
      point.x >= box.x &&
      point.x <= box.x + box.width &&
      point.y >= box.y &&
      point.y <= box.y + box.height
    ) {
      return { layer, mode: 'move' as const }
    }
  }

  return null
}

function beginTextInteraction(event: PointerEvent) {
  const canvas = canvasRef.value
  if (!canvas) return false

  const point = pointerPosition(event)
  const hit = hitTextLayer(point)
  if (!hit) {
    selectedTextLayerId.value = null
    render()
    return false
  }

  selectedTextLayerId.value = hit.layer.id
  textInteraction.value = {
    mode: hit.mode,
    layerId: hit.layer.id,
    startX: point.x,
    startY: point.y,
    originalX: hit.layer.x,
    originalY: hit.layer.y,
    originalFontSize: hit.layer.fontSize
  }
  canvas.setPointerCapture(event.pointerId)
  render()
  return true
}

function updateTextInteraction(event: PointerEvent) {
  const interaction = textInteraction.value
  const canvas = canvasRef.value
  if (!interaction || !canvas) return

  const point = pointerPosition(event)
  const dx = point.x - interaction.startX
  const dy = point.y - interaction.startY

  emit('update:textLayers', props.textLayers.map(layer => {
    if (layer.id !== interaction.layerId) return layer

    if (interaction.mode === 'move') {
      return {
        ...layer,
        x: Math.min(1, Math.max(0, interaction.originalX + dx / canvas.width)),
        y: Math.min(1, Math.max(0, interaction.originalY + dy / canvas.height))
      }
    }

    const scaleDelta = (dx + dy) / 2 / (canvas.width / image.naturalWidth)
    return {
      ...layer,
      fontSize: Math.min(240, Math.max(12, Math.round(interaction.originalFontSize + scaleDelta)))
    }
  }))
}

function endTextInteraction(event: PointerEvent) {
  if (!textInteraction.value) return
  textInteraction.value = null
  canvasRef.value?.releasePointerCapture(event.pointerId)
}

function isMaskDrawingMode() {
  return props.taskMode === 'local_edit' || (props.taskMode === 'text_layer' && props.textTool === 'erase')
}

function pointerPosition(event: PointerEvent) {
  const canvas = canvasRef.value!
  const rect = canvas.getBoundingClientRect()
  return {
    x: (event.clientX - rect.left) * canvas.width / rect.width,
    y: (event.clientY - rect.top) * canvas.height / rect.height
  }
}

function beginDraw(event: PointerEvent) {
  if (props.taskMode === 'text_layer' && props.textTool === 'select') {
    beginTextInteraction(event)
    return
  }
  if (!isMaskDrawingMode() || !canvasRef.value) return
  const ctx = maskCanvas.getContext('2d')
  if (!ctx) return

  undoStack.push(ctx.getImageData(0, 0, maskCanvas.width, maskCanvas.height))
  if (undoStack.length > 20) undoStack.shift()

  isDrawing.value = true
  canvasRef.value.setPointerCapture(event.pointerId)
  const point = pointerPosition(event)
  ctx.beginPath()
  ctx.moveTo(point.x, point.y)
  drawTo(event)
}

function drawTo(event: PointerEvent) {
  if (textInteraction.value) {
    updateTextInteraction(event)
    return
  }
  if (!isDrawing.value || !isMaskDrawingMode()) return
  const ctx = maskCanvas.getContext('2d')
  if (!ctx) return

  const point = pointerPosition(event)
  ctx.globalCompositeOperation = props.maskTool === 'erase' ? 'destination-out' : 'source-over'
  ctx.lineWidth = props.brushSize
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.strokeStyle = '#ffffff'
  ctx.lineTo(point.x, point.y)
  ctx.stroke()
  ctx.globalCompositeOperation = 'source-over'
  hasMask.value = true
  render()
}

function endDraw(event: PointerEvent) {
  if (textInteraction.value) {
    endTextInteraction(event)
    return
  }
  if (!isDrawing.value) return
  isDrawing.value = false
  canvasRef.value?.releasePointerCapture(event.pointerId)
  hasMask.value = !isMaskEmpty()
  render()
}

function clearMask() {
  const ctx = maskCanvas.getContext('2d')
  if (!ctx) return
  ctx.clearRect(0, 0, maskCanvas.width, maskCanvas.height)
  undoStack.length = 0
  hasMask.value = false
  render()
}

function undoMask() {
  const previous = undoStack.pop()
  const ctx = maskCanvas.getContext('2d')
  if (!previous || !ctx) return
  ctx.putImageData(previous, 0, 0)
  hasMask.value = undoStack.length > 0 || !isMaskEmpty()
  render()
}

function isMaskEmpty() {
  const ctx = maskCanvas.getContext('2d')
  if (!ctx) return true
  const data = ctx.getImageData(0, 0, maskCanvas.width, maskCanvas.height).data
  for (let i = 3; i < data.length; i += 4) {
    if (data[i] > 0) return false
  }
  return true
}

async function exportCompositeImage() {
  if (!imageReady.value) throw new Error('图片尚未加载完成')

  const output = document.createElement('canvas')
  output.width = image.naturalWidth
  output.height = image.naturalHeight
  const ctx = output.getContext('2d')
  if (!ctx) throw new Error('无法创建画布')

  ctx.drawImage(image, 0, 0, output.width, output.height)
  if (props.taskMode === 'text_layer' && hasMask.value) {
    const erased = createErasedCanvas(output.width, output.height)
    if (erased) ctx.drawImage(erased, 0, 0)
  }
  renderTextLayers(ctx, output.width, output.height)

  const blob = await canvasToBlob(output)
  return new File([blob], 'canvas_result.png', { type: 'image/png' })
}

async function exportMaskImage() {
  if (!imageReady.value || !hasMask.value) return null

  const output = document.createElement('canvas')
  output.width = image.naturalWidth
  output.height = image.naturalHeight
  const ctx = output.getContext('2d')
  if (!ctx) throw new Error('无法创建遮罩')

  ctx.fillStyle = '#000000'
  ctx.fillRect(0, 0, output.width, output.height)
  if (props.maskFeather > 0) {
    ctx.filter = `blur(${props.maskFeather}px)`
  }
  ctx.drawImage(maskCanvas, 0, 0, output.width, output.height)
  ctx.filter = 'none'

  const blob = await canvasToBlob(output)
  return new File([blob], 'mask.png', { type: 'image/png' })
}

function canvasToBlob(canvas: HTMLCanvasElement) {
  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(blob => {
      if (blob) resolve(blob)
      else reject(new Error('画布导出失败'))
    }, 'image/png')
  })
}

defineExpose({
  exportCompositeImage,
  exportMaskImage,
  clearMask,
  undoMask
})
</script>

<template>
  <div class="rounded-card bg-white overflow-hidden border border-line">
    <canvas
      ref="canvasRef"
      class="w-full block touch-none"
      :class="taskMode === 'local_edit' ? 'cursor-crosshair' : ''"
      @pointerdown="beginDraw"
      @pointermove="drawTo"
      @pointerup="endDraw"
      @pointercancel="endDraw"
    />
  </div>
</template>
