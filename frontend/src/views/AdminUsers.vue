<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getAdminUsers } from '@/api'
import type { AdminUserListItem } from '@/types'

const router = useRouter()

const users = ref<AdminUserListItem[]>([])
const loading = ref(false)
const search = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const error = ref('')

onMounted(() => {
  loadUsers()
})

async function loadUsers(resetPage = false) {
  if (resetPage) page.value = 1
  loading.value = true
  error.value = ''

  try {
    const data = await getAdminUsers(page.value, pageSize.value, search.value.trim())
    users.value = data.items
    total.value = data.total
  } catch (e: any) {
    error.value = e.message || '加载用户失败'
  } finally {
    loading.value = false
  }
}

function openUser(userId: number) {
  router.push(`/admin/users/${userId}`)
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
      <header class="mb-5 flex flex-col gap-4 sm:mb-6 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p class="mb-1 text-[12px] font-medium text-ink-muted">管理后台</p>
          <h1 class="text-[24px] font-semibold leading-tight text-ink sm:text-[28px]">用户管理</h1>
        </div>

        <form class="flex gap-2" @submit.prevent="loadUsers(true)">
          <input
            v-model="search"
            class="dk-input rounded-lg sm:w-72"
            placeholder="搜索用户名或手机号"
          />
          <button class="dk-btn-primary shrink-0 rounded-lg" type="submit">搜索</button>
        </form>
      </header>

      <div v-if="error" class="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-600">
        {{ error }}
      </div>

      <section class="rounded-card border border-line bg-white shadow-hover">
        <div class="flex items-center justify-between border-b border-line px-4 py-3">
          <span class="text-[13px] font-medium text-ink-soft">共 {{ total }} 个用户</span>
          <button class="dk-btn-ghost" :disabled="loading" @click="loadUsers()">刷新</button>
        </div>

        <div v-if="loading" class="p-12 text-center text-[13px] text-ink-muted">加载中...</div>
        <div v-else-if="users.length === 0" class="p-12 text-center text-[13px] text-ink-muted">暂无用户</div>

        <div v-else>
          <div class="hidden overflow-x-auto md:block">
            <table class="w-full min-w-[760px] text-left text-[13px]">
              <thead class="bg-canvas text-ink-muted">
                <tr>
                  <th class="px-4 py-3 font-medium">用户</th>
                  <th class="px-4 py-3 font-medium">手机号</th>
                  <th class="px-4 py-3 font-medium">状态</th>
                  <th class="px-4 py-3 font-medium">会话</th>
                  <th class="px-4 py-3 font-medium">记录</th>
                  <th class="px-4 py-3 font-medium">最近活跃</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="user in users"
                  :key="user.id"
                  class="cursor-pointer border-t border-line transition-colors hover:bg-selected/50"
                  @click="openUser(user.id)"
                >
                  <td class="px-4 py-3">
                    <div class="font-medium text-ink">{{ user.username }}</div>
                    <div class="text-[12px] text-ink-muted">ID {{ user.id }}<span v-if="user.is_admin"> · 管理员</span></div>
                  </td>
                  <td class="px-4 py-3 text-ink-soft">{{ user.phone || '未绑定' }}</td>
                  <td class="px-4 py-3">
                    <span
                      class="rounded-full px-2 py-1 text-[12px]"
                      :class="user.is_active ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'"
                    >
                      {{ user.is_active ? '启用' : '禁用' }}
                    </span>
                  </td>
                  <td class="px-4 py-3 text-ink-soft">{{ user.session_count }}</td>
                  <td class="px-4 py-3 text-ink-soft">{{ user.record_count }}</td>
                  <td class="px-4 py-3 text-ink-soft">{{ formatDate(user.last_active_at) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="divide-y divide-line md:hidden">
            <article
              v-for="user in users"
              :key="user.id"
              class="p-4"
              @click="openUser(user.id)"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="truncate text-[15px] font-semibold text-ink">{{ user.username }}</p>
                  <p class="mt-1 text-[12px] text-ink-muted">ID {{ user.id }} · {{ user.phone || '未绑定手机号' }}</p>
                </div>
                <span
                  class="shrink-0 rounded-full px-2 py-1 text-[12px]"
                  :class="user.is_active ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'"
                >
                  {{ user.is_active ? '启用' : '禁用' }}
                </span>
              </div>
              <div class="mt-3 grid grid-cols-3 gap-2 text-[12px] text-ink-soft">
                <div class="rounded-lg bg-canvas px-2 py-2">会话 {{ user.session_count }}</div>
                <div class="rounded-lg bg-canvas px-2 py-2">记录 {{ user.record_count }}</div>
                <div class="rounded-lg bg-canvas px-2 py-2">{{ user.is_admin ? '管理员' : '普通用户' }}</div>
              </div>
            </article>
          </div>
        </div>
      </section>

      <div v-if="!loading && total > pageSize" class="mt-6 flex items-center justify-center gap-3">
        <button
          class="dk-btn-ghost"
          :disabled="page === 1"
          :class="{ 'opacity-40 cursor-not-allowed': page === 1 }"
          @click="page--; loadUsers()"
        >
          上一页
        </button>
        <span class="text-[13px] text-ink-muted">{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
        <button
          class="dk-btn-ghost"
          :disabled="page >= Math.ceil(total / pageSize)"
          :class="{ 'opacity-40 cursor-not-allowed': page >= Math.ceil(total / pageSize) }"
          @click="page++; loadUsers()"
        >
          下一页
        </button>
      </div>
    </div>
  </div>
</template>
