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
const pageSize = ref(10)
const total = ref(0)
const error = ref('')

onMounted(() => loadUsers())

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
  return new Date(dateStr).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}
</script>

<template>
  <div class="admin-page">
    <div class="admin-shell">
      <header class="admin-header">
        <div>
          <p class="admin-eyebrow">ADMINISTRATION</p>
          <h1>用户管理</h1>
          <p class="admin-lede">管理账号状态，并查看用户的图像编辑记录。</p>
        </div>
        <form class="search-form" @submit.prevent="loadUsers(true)">
          <label class="search-box">
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none"><circle cx="10.8" cy="10.8" r="6.8" stroke="currentColor" stroke-width="1.7"/><path d="m16 16 4.2 4.2" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>
            <input v-model="search" type="search" placeholder="搜索用户名或手机号" aria-label="搜索用户名或手机号" />
          </label>
          <button type="submit" class="search-button">搜索</button>
        </form>
      </header>

      <div v-if="error" class="admin-error" role="alert">{{ error }}</div>

      <section class="user-directory" aria-label="用户列表">
        <div class="directory-toolbar">
          <div><strong>{{ total }}</strong><span>位用户</span></div>
          <button class="refresh-button" type="button" :disabled="loading" @click="loadUsers()">
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none"><path d="M20 11a8 8 0 0 0-14.8-3M4 4v4h4m-4 5a8 8 0 0 0 14.8 3M20 20v-4h-4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>
            刷新
          </button>
        </div>

        <div v-if="loading" class="directory-state">正在加载用户…</div>
        <div v-else-if="users.length === 0" class="directory-state">没有找到用户</div>

        <div v-else>
          <div class="desktop-table-wrap">
            <table class="user-table">
              <thead>
                <tr><th>用户</th><th>账号状态</th><th>会话</th><th>编辑记录</th><th>最近活跃</th><th><span class="sr-only">操作</span></th></tr>
              </thead>
              <tbody>
                <tr v-for="user in users" :key="user.id">
                  <td>
                    <div class="user-cell">
                      <span class="user-avatar">{{ user.username.slice(0, 1).toUpperCase() }}</span>
                      <span class="user-copy"><strong>{{ user.username }}</strong><small>ID {{ user.id }}<template v-if="user.is_admin"> · 管理员</template><template v-if="user.phone"> · {{ user.phone }}</template></small></span>
                    </div>
                  </td>
                  <td><span class="account-state" :class="user.is_active ? 'enabled' : 'disabled'"><i></i>{{ user.is_active ? '启用' : '已禁用' }}</span></td>
                  <td class="numeric-cell">{{ user.session_count }}</td>
                  <td class="numeric-cell">{{ user.record_count }}</td>
                  <td class="date-cell">{{ formatDate(user.last_active_at) }}</td>
                  <td class="action-cell"><button type="button" @click="openUser(user.id)">查看记录 <span aria-hidden="true">›</span></button></td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="mobile-users">
            <article v-for="user in users" :key="user.id" class="mobile-user">
              <div class="mobile-user-main">
                <span class="user-avatar">{{ user.username.slice(0, 1).toUpperCase() }}</span>
                <div class="user-copy"><strong>{{ user.username }}</strong><small>ID {{ user.id }} · {{ user.phone || '未绑定手机号' }}</small></div>
                <span class="account-state" :class="user.is_active ? 'enabled' : 'disabled'"><i></i>{{ user.is_active ? '启用' : '禁用' }}</span>
              </div>
              <div class="mobile-user-stats"><span>{{ user.session_count }} 个会话</span><span>{{ user.record_count }} 条编辑记录</span><span>活跃于 {{ formatDate(user.last_active_at) }}</span></div>
              <button type="button" class="mobile-detail-button" @click="openUser(user.id)">查看使用记录 <span aria-hidden="true">›</span></button>
            </article>
          </div>
        </div>
      </section>

      <nav v-if="!loading && total > pageSize" class="pagination" aria-label="用户列表分页">
        <button type="button" :disabled="page === 1" @click="page--; loadUsers()">上一页</button>
        <span>{{ page }} <i>/</i> {{ Math.ceil(total / pageSize) }}</span>
        <button type="button" :disabled="page >= Math.ceil(total / pageSize)" @click="page++; loadUsers()">下一页</button>
      </nav>
    </div>
  </div>
</template>

<style scoped>
.admin-page { min-height: 100vh; background: #f5f5f7; color: #1d1d1f; padding: 52px 28px 96px; }
.admin-shell { max-width: 1180px; margin: 0 auto; }
.admin-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 28px; margin-bottom: 37px; }
.admin-eyebrow { color: #86868b; font-size: 11px; font-weight: 700; letter-spacing: 0; margin: 0 0 10px; }
.admin-header h1 { font-size: 46px; line-height: 1.05; letter-spacing: 0; margin: 0; }
.admin-lede { color: #6e6e73; font-size: 14px; margin: 13px 0 0; }
.search-form { display: flex; gap: 9px; width: min(430px, 100%); }
.search-box { display: flex; align-items: center; gap: 9px; flex: 1; min-width: 0; background: white; border: 1px solid #d2d2d7; border-radius: 8px; padding: 0 12px; }
.search-box:focus-within { border-color: #0071e3; box-shadow: 0 0 0 3px rgba(0,113,227,.12); }
.search-box svg { width: 17px; height: 17px; color: #86868b; flex: none; }
.search-box input { min-width: 0; width: 100%; height: 42px; border: 0; outline: 0; background: transparent; color: #1d1d1f; font-size: 13px; }
.search-button { border: 0; border-radius: 999px; background: #0071e3; color: white; font-size: 13px; font-weight: 600; padding: 0 20px; cursor: pointer; }
.admin-error { color: #b42318; background: #fff2f0; border: 1px solid #ffd7d2; border-radius: 8px; padding: 12px 14px; font-size: 13px; margin-bottom: 18px; }
.user-directory { background: white; border-radius: 8px; overflow: hidden; border: 1px solid #e8e8ed; }
.directory-toolbar { display: flex; align-items: center; justify-content: space-between; min-height: 56px; padding: 0 22px; border-bottom: 1px solid #e8e8ed; color: #6e6e73; font-size: 13px; }
.directory-toolbar strong { color: #1d1d1f; font-size: 16px; margin-right: 5px; }
.refresh-button { display: inline-flex; align-items: center; gap: 6px; border: 0; background: transparent; color: #0071e3; font-size: 12px; cursor: pointer; }
.refresh-button svg { width: 15px; height: 15px; }
.refresh-button:disabled { opacity: .5; cursor: wait; }
.directory-state { color: #86868b; text-align: center; padding: 72px 20px; font-size: 13px; }
.desktop-table-wrap { overflow-x: auto; }
.user-table { width: 100%; table-layout: fixed; border-collapse: collapse; text-align: left; white-space: nowrap; }
.user-table th { height: 44px; padding: 0 18px; color: #86868b; background: #fafafa; font-size: 11px; font-weight: 600; }
.user-table td { height: 69px; padding: 8px 18px; border-top: 1px solid #f0f0f2; font-size: 12px; }
.user-table th:nth-child(1) { width: 34%; }
.user-table th:nth-child(2) { width: 15%; }
.user-table th:nth-child(3), .user-table th:nth-child(4) { width: 9%; }
.user-table th:nth-child(5) { width: 16%; }
.user-table th:nth-child(6) { width: 17%; }
.user-table tbody tr:hover { background: #fafafa; }
.user-cell, .mobile-user-main { display: flex; align-items: center; gap: 12px; }
.user-avatar { display: grid; place-items: center; flex: none; width: 38px; height: 38px; border-radius: 8px; color: #fff; background: #1d1d1f; font-size: 15px; font-weight: 600; }
.user-copy { display: grid; gap: 4px; min-width: 0; }
.user-copy strong { overflow: hidden; color: #1d1d1f; font-size: 13px; font-weight: 600; text-overflow: ellipsis; }
.user-copy small { overflow: hidden; color: #86868b; font-size: 11px; text-overflow: ellipsis; }
.account-state { display: inline-flex; align-items: center; gap: 6px; font-size: 11px; }
.account-state i { display: block; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.account-state.enabled { color: #248a49; }
.account-state.disabled { color: #c43d32; }
.numeric-cell { color: #424245; font-variant-numeric: tabular-nums; }
.date-cell { color: #6e6e73; }
.action-cell { text-align: right; }
.action-cell button { padding: 8px 0 8px 8px; }
.action-cell button, .mobile-detail-button { border: 0; background: transparent; color: #0071e3; font-size: 12px; font-weight: 600; cursor: pointer; white-space: nowrap; }
.action-cell button span, .mobile-detail-button span { font-size: 20px; vertical-align: -1px; margin-left: 3px; }
.mobile-users { display: none; }
.pagination { display: flex; align-items: center; justify-content: center; gap: 18px; margin-top: 23px; }
.pagination button { border: 0; background: transparent; color: #0071e3; font-size: 12px; padding: 8px; cursor: pointer; }
.pagination button:disabled { color: #b8b8bd; cursor: not-allowed; }
.pagination span { color: #424245; font-size: 12px; font-variant-numeric: tabular-nums; }
.pagination i { color: #a1a1a6; font-style: normal; margin: 0 5px; }
@media (max-width: 760px) {
  .admin-page { padding: 32px 16px 88px; }
  .admin-header h1 { font-size: 36px; }
  .admin-header { align-items: stretch; flex-direction: column; margin-bottom: 25px; }
  .search-form { width: 100%; }
  .directory-toolbar { padding: 0 15px; }
  .desktop-table-wrap { display: none; }
  .mobile-users { display: block; }
  .mobile-user { padding: 16px 15px 12px; border-bottom: 1px solid #f0f0f2; }
  .mobile-user-main { gap: 10px; }
  .mobile-user-main .user-copy { flex: 1; }
  .mobile-user .user-avatar { width: 36px; height: 36px; }
  .mobile-user-stats { display: flex; flex-wrap: wrap; gap: 7px 14px; color: #86868b; font-size: 10px; padding: 13px 0 8px 46px; }
  .mobile-detail-button { margin-left: 46px; padding: 3px 0; }
}
</style>
