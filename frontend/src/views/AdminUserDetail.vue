<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  deleteAdminSession,
  getAdminSession,
  getAdminUser,
  getAdminUserHistory,
  updateAdminUser
} from '@/api'
import type { AdminSessionDetailResponse, AdminUserDetail, SessionListItem } from '@/types'

const route = useRoute()
const router = useRouter()

const user = ref<AdminUserDetail | null>(null)
const sessions = ref<SessionListItem[]>([])
const selectedSession = ref<AdminSessionDetailResponse | null>(null)
const username = ref('')
const phone = ref('')
const isActive = ref(true)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const loading = ref(false)
const saving = ref(false)
const historyLoading = ref(false)
const error = ref('')
const message = ref('')

const userId = computed(() => Number(route.params.userId))

onMounted(async () => {
  await loadAll()
})

async function loadAll() {
  await Promise.all([loadUser(), loadHistory()])
}

async function loadUser() {
  loading.value = true
  error.value = ''
  try {
    user.value = await getAdminUser(userId.value)
    username.value = user.value.username
    phone.value = user.value.phone || ''
    isActive.value = user.value.is_active
  } catch (e: any) {
    error.value = e.message || '加载用户失败'
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const data = await getAdminUserHistory(userId.value, page.value, pageSize.value)
    sessions.value = data.items
    total.value = data.total
  } catch (e: any) {
    error.value = e.message || '加载历史失败'
  } finally {
    historyLoading.value = false
  }
}

async function saveUser() {
  if (saving.value) return
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    user.value = await updateAdminUser(userId.value, {
      username: username.value.trim(),
      phone: phone.value.trim(),
      is_active: isActive.value
    })
    message.value = '用户信息已保存'
  } catch (e: any) {
    error.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function openSession(sessionId: string) {
  selectedSession.value = await getAdminSession(sessionId)
}

async function removeSession(sessionId: string) {
  if (!confirm('确定删除这个会话吗？关联图片文件也会被删除。')) return
  await deleteAdminSession(sessionId)
  if (selectedSession.value?.session.id === sessionId) {
    selectedSession.value = null
  }
  await loadHistory()
  await loadUser()
}

function formatDate(dateStr?: string) {
  if (!dateStr) return '暂无'
  return new Date(dateStr).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<template>
  <div class="min-h-screen px-4 py-5 sm:px-6 sm:py-8 lg:px-8">
    <div class="mx-auto max-w-6xl">
      <header class="mb-5 flex items-center gap-3 sm:mb-6">
        <button class="dk-btn-ghost rounded-lg" @click="router.push('/admin/users')">返回</button>
        <div class="min-w-0">
          <p class="mb-1 text-[12px] font-medium text-ink-muted">用户管理</p>
          <h1 class="truncate text-[24px] font-semibold leading-tight text-ink sm:text-[28px]">
            {{ user?.username || '用户详情' }}
          </h1>
        </div>
      </header>

      <div v-if="error" class="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-600">
        {{ error }}
      </div>
      <div v-if="message" class="mb-4 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-[13px] text-green-700">
        {{ message }}
      </div>

      <div class="grid gap-5 lg:grid-cols-[360px_1fr]">
        <section class="rounded-card border border-line bg-white p-4 shadow-hover sm:p-5">
          <div class="mb-4">
            <h2 class="text-[18px] font-semibold text-ink">基础信息</h2>
            <p class="mt-1 text-[13px] text-ink-muted">管理员可修改用户资料和账号状态。</p>
          </div>

          <form class="space-y-4" @submit.prevent="saveUser">
            <label class="block">
              <span class="mb-1.5 block text-[13px] font-medium text-ink-soft">用户名</span>
              <input
                v-model="username"
                class="dk-input rounded-lg"
                required
                minlength="1"
                maxlength="15"
                pattern="[\u4e00-\u9fa5A-Za-z0-9]{1,15}"
              />
            </label>

            <label class="block">
              <span class="mb-1.5 block text-[13px] font-medium text-ink-soft">手机号</span>
              <input
                v-model="phone"
                class="dk-input rounded-lg"
                required
                type="tel"
                inputmode="numeric"
                minlength="11"
                maxlength="11"
                pattern="1[3-9][0-9]{9}"
              />
            </label>

            <label class="flex items-center justify-between rounded-lg border border-line px-3 py-2">
              <span class="text-[13px] font-medium text-ink-soft">账号启用</span>
              <input v-model="isActive" type="checkbox" class="h-4 w-4 accent-brand" />
            </label>

            <div class="grid grid-cols-2 gap-2 text-[12px] text-ink-soft">
              <div class="rounded-lg bg-canvas px-3 py-2">会话 {{ user?.session_count ?? 0 }}</div>
              <div class="rounded-lg bg-canvas px-3 py-2">记录 {{ user?.record_count ?? 0 }}</div>
              <div class="rounded-lg bg-canvas px-3 py-2">{{ user?.is_admin ? '管理员' : '普通用户' }}</div>
              <div class="rounded-lg bg-canvas px-3 py-2">{{ user?.is_active ? '启用' : '禁用' }}</div>
            </div>

            <button type="submit" class="dk-btn-primary w-full rounded-lg py-3" :disabled="saving || loading">
              {{ saving ? '保存中...' : '保存用户' }}
            </button>
          </form>
        </section>

        <section class="rounded-card border border-line bg-white shadow-hover">
          <div class="flex items-center justify-between border-b border-line px-4 py-3">
            <div>
              <h2 class="text-[18px] font-semibold text-ink">历史会话</h2>
              <p class="text-[12px] text-ink-muted">共 {{ total }} 个会话</p>
            </div>
            <button class="dk-btn-ghost" :disabled="historyLoading" @click="loadHistory()">刷新</button>
          </div>

          <div v-if="historyLoading" class="p-10 text-center text-[13px] text-ink-muted">加载中...</div>
          <div v-else-if="sessions.length === 0" class="p-10 text-center text-[13px] text-ink-muted">暂无历史会话</div>

          <div v-else class="divide-y divide-line">
            <article
              v-for="session in sessions"
              :key="session.id"
              class="grid gap-3 p-4 sm:grid-cols-[96px_1fr_auto] sm:items-center"
            >
              <div class="aspect-[4/3] overflow-hidden rounded-lg bg-canvas">
                <img
                  v-if="session.last_result_url"
                  :src="session.last_result_url"
                  :alt="session.title || ''"
                  class="h-full w-full object-cover"
                  loading="lazy"
                />
              </div>
              <div class="min-w-0">
                <p class="truncate text-[15px] font-semibold text-ink">{{ session.title || '未命名会话' }}</p>
                <p class="mt-1 text-[12px] text-ink-muted">
                  {{ session.record_count }} 轮编辑 · {{ formatDate(session.updated_at) }}
                </p>
              </div>
              <div class="flex gap-2">
                <button class="dk-btn-ghost" @click="openSession(session.id)">查看</button>
                <button class="dk-btn-ghost text-red-500 hover:text-red-600" @click="removeSession(session.id)">删除</button>
              </div>
            </article>
          </div>

          <div v-if="!historyLoading && total > pageSize" class="flex items-center justify-center gap-3 border-t border-line p-4">
            <button
              class="dk-btn-ghost"
              :disabled="page === 1"
              :class="{ 'opacity-40 cursor-not-allowed': page === 1 }"
              @click="page--; loadHistory()"
            >
              上一页
            </button>
            <span class="text-[13px] text-ink-muted">{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
            <button
              class="dk-btn-ghost"
              :disabled="page >= Math.ceil(total / pageSize)"
              :class="{ 'opacity-40 cursor-not-allowed': page >= Math.ceil(total / pageSize) }"
              @click="page++; loadHistory()"
            >
              下一页
            </button>
          </div>
        </section>
      </div>

      <section v-if="selectedSession" class="mt-5 rounded-card border border-line bg-white p-4 shadow-hover sm:p-5">
        <div class="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 class="text-[18px] font-semibold text-ink">{{ selectedSession.session.title || '会话详情' }}</h2>
            <p class="mt-1 text-[12px] text-ink-muted">会话 ID：{{ selectedSession.session.id }}</p>
          </div>
          <button class="dk-btn-ghost" @click="selectedSession = null">收起</button>
        </div>

        <div class="space-y-3">
          <article
            v-for="record in selectedSession.session.records"
            :key="record.id"
            class="rounded-lg border border-line p-3"
          >
            <p class="text-[13px] font-medium text-ink">#{{ record.id }} {{ record.instruction }}</p>
            <p class="mt-1 text-[12px] text-ink-muted">
              {{ record.provider }} · {{ record.model }} · {{ record.status }} · {{ formatDate(record.created_at) }}
            </p>
            <div v-if="record.result_urls?.length" class="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
              <img
                v-for="url in record.result_urls"
                :key="url"
                :src="url"
                class="aspect-[4/3] w-full rounded-lg object-cover"
                loading="lazy"
              />
            </div>
          </article>
        </div>
      </section>
    </div>
  </div>
</template>
