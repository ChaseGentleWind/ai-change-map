<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getSessions, deleteSession } from '@/api'
import type { SessionListItem } from '@/types'

const sessions = ref<SessionListItem[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

onMounted(() => {
  loadSessions()
})

async function loadSessions() {
  loading.value = true
  try {
    const data = await getSessions(page.value, pageSize.value)
    sessions.value = data.items
    total.value = data.total
  } catch (e) {
    console.error('加载历史记录失败:', e)
  } finally {
    loading.value = false
  }
}

async function handleDelete(sessionId: string) {
  if (!confirm('确定删除这个会话吗？')) return

  try {
    await deleteSession(sessionId)
    await loadSessions()
  } catch (e) {
    alert('删除失败')
  }
}

function formatDate(dateStr: string) {
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  })
}
</script>

<template>
  <div class="min-h-screen">
    <!-- 顶部 bar -->
    <header class="sticky top-0 z-10 bg-canvas/80 backdrop-blur border-b border-line/60">
      <div class="max-w-[1400px] mx-auto px-8 py-4 flex items-center gap-6">
        <h1 class="text-[18px] font-semibold text-ink shrink-0">历史会话</h1>
        <span class="text-[12px] text-ink-muted">共 {{ total }} 个会话</span>
        <div class="ml-auto">
          <router-link to="/" class="dk-btn-primary">
            <svg class="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15"/>
            </svg>
            新建编辑
          </router-link>
        </div>
      </div>
    </header>

    <div class="max-w-[1400px] mx-auto px-8 py-6">
      <!-- loading -->
      <div v-if="loading" class="dk-card p-16 text-center">
        <svg class="animate-spin h-8 w-8 text-brand mx-auto mb-3" viewBox="0 0 24 24" fill="none">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
        <p class="text-ink-muted text-[13px]">加载中...</p>
      </div>

      <!-- empty -->
      <div v-else-if="sessions.length === 0" class="dk-card p-16 text-center">
        <div class="w-14 h-14 rounded-2xl bg-white border border-line mx-auto mb-4 flex items-center justify-center">
          <svg class="w-6 h-6 text-ink-faint" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.6">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"/>
          </svg>
        </div>
        <p class="text-ink font-medium text-[14px] mb-1">暂无历史记录</p>
        <p class="text-ink-muted text-[12px]">完成第一次编辑后会自动出现在这里</p>
      </div>

      <!-- 卡片网格：等宽 4 列，每张约 292px -->
      <div v-else class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        <article
          v-for="session in sessions"
          :key="session.id"
          class="dk-card-hover p-3 cursor-pointer"
          @click="$router.push({ path: '/', query: { sessionId: session.id } })"
        >
          <!-- 预览图 -->
          <div class="aspect-[4/3] rounded-xl bg-white overflow-hidden mb-3">
            <img
              v-if="session.last_result_url"
              :src="session.last_result_url"
              :alt="session.title || ''"
              class="w-full h-full object-cover"
              loading="lazy"
            />
            <div v-else class="w-full h-full flex items-center justify-center text-ink-faint">
              <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.4">
                <path stroke-linecap="round" stroke-linejoin="round" d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 0 0 1.5-1.5V6a1.5 1.5 0 0 0-1.5-1.5H3.75A1.5 1.5 0 0 0 2.25 6v12a1.5 1.5 0 0 0 1.5 1.5Zm10.5-11.25h.008v.008h-.008V8.25Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z"/>
              </svg>
            </div>
          </div>

          <!-- 信息 -->
          <h3 class="dk-tool-title truncate mb-1">
            {{ session.title || '未命名会话' }}
          </h3>
          <div class="flex items-center justify-between">
            <p class="dk-tool-desc">
              {{ session.record_count }} 轮编辑 · {{ formatDate(session.created_at) }}
            </p>
            <button
              class="text-[11px] text-ink-faint hover:text-red-500 transition-colors px-1"
              title="删除"
              @click.stop="handleDelete(session.id)"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.8">
                <path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"/>
              </svg>
            </button>
          </div>
        </article>
      </div>

      <!-- 分页 -->
      <div v-if="!loading && total > pageSize" class="mt-8 flex items-center justify-center gap-3">
        <button
          class="dk-btn-ghost"
          :disabled="page === 1"
          :class="{ 'opacity-40 cursor-not-allowed': page === 1 }"
          @click="page--; loadSessions()"
        >
          上一页
        </button>
        <span class="text-[13px] text-ink-muted">
          {{ page }} / {{ Math.ceil(total / pageSize) }}
        </span>
        <button
          class="dk-btn-ghost"
          :disabled="page >= Math.ceil(total / pageSize)"
          :class="{ 'opacity-40 cursor-not-allowed': page >= Math.ceil(total / pageSize) }"
          @click="page++; loadSessions()"
        >
          下一页
        </button>
      </div>
    </div>
  </div>
</template>
