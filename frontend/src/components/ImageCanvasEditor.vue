<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import type { TaskMode, TextLayer } from '@/types'

const props = defineProps<{
  imageSrc: string
  taskMode: TaskMode
  textLayers: TextLayer[]
  brushSize: number
  maskSrc?: string
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const maskCanvas = document.createElement('canvas')
const image = new Image()
const imageReady = ref(false)
const isDrawing = ref(false)
const hasMask = ref(false)
const undoStack: ImageData[] = []

watch(
  () => props.imageSrc,
  () => {
    loadImage()
  },
  { immediate: true }
)

watch(
  () => [props.taskMode, props.textLayers, props.brushSize],
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
    ctx.save()
    ctx.globalAlpha = 0.38
    ctx.drawImage(maskCanvas, 0, 0)
    ctx.restore()
  }

  renderTextLayers(ctx, canvas.width, canvas.height)
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

function pointerPosition(event: PointerEvent) {
  const canvas = canvasRef.value!
  const rect = canvas.getBoundingClientRect()
  return {
    x: (event.clientX - rect.left) * canvas.width / rect.width,
    y: (event.clientY - rect.top) * canvas.height / rect.height
  }
}

function beginDraw(event: PointerEvent) {
  if (props.taskMode !== 'local_edit' || !canvasRef.value) return
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
  if (!isDrawing.value || props.taskMode !== 'local_edit') return
  const ctx = maskCanvas.getContext('2d')
  if (!ctx) return

  const point = pointerPosition(event)
  ctx.lineWidth = props.brushSize
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.strokeStyle = '#ffffff'
  ctx.lineTo(point.x, point.y)
  ctx.stroke()
  hasMask.value = true
  render()
}

function endDraw(event: PointerEvent) {
  if (!isDrawing.value) return
  isDrawing.value = false
  canvasRef.value?.releasePointerCapture(event.pointerId)
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
  ctx.drawImage(maskCanvas, 0, 0, output.width, output.height)

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
