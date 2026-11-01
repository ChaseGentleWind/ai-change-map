<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { deleteAdminSession, getAdminSession, getAdminUser, getAdminUserHistory, updateAdminUser } from '@/api'
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
const pageSize = ref(10)
const total = ref(0)
const loading = ref(false)
const saving = ref(false)
const historyLoading = ref(false)
const error = ref('')
const message = ref('')
const userId = computed(() => Number(route.params.userId))

onMounted(loadAll)

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
      username: username.value.trim(), phone: phone.value.trim(), is_active: isActive.value
    })
    message.value = '用户信息已保存'
  } catch (e: any) {
    error.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function openSession(sessionId: string) {
  try {
    selectedSession.value = await getAdminSession(sessionId)
  } catch (e: any) {
    error.value = e.message || '加载会话详情失败'
  }
}

async function removeSession(sessionId: string) {
  if (!confirm('确定删除这个会话吗？关联的图片记录也会一并删除。')) return
  try {
    await deleteAdminSession(sessionId)
    if (selectedSession.value?.session.id === sessionId) selectedSession.value = null
    await Promise.all([loadHistory(), loadUser()])
  } catch (e: any) {
    error.value = e.message || '删除会话失败'
  }
}

function formatDate(dateStr?: string) {
  if (!dateStr) return '暂无'
  return new Date(dateStr).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
  })
}
</script>

<template>
  <div class="detail-page">
    <div class="detail-shell">
      <header class="detail-header">
        <div>
          <button class="back-link" type="button" @click="router.push('/admin/users')"><span aria-hidden="true">‹</span> 用户列表</button>
          <p class="detail-eyebrow">USER ACCOUNT</p>
          <h1>{{ user?.username || '用户详情' }}</h1>
          <p class="detail-subtitle">用户使用记录与账号设置</p>
        </div>
        <div v-if="user" class="detail-user-mark">
          <span class="user-avatar">{{ user.username.slice(0, 1).toUpperCase() }}</span>
          <span><strong>ID {{ user.id }}</strong><small>{{ user.is_admin ? '管理员账号' : '普通用户' }}</small></span>
        </div>
      </header>

      <div v-if="error" class="detail-alert" role="alert">{{ error }}</div>
      <div v-if="message" class="detail-success" role="status">{{ message }}</div>

      <section class="account-panel">
          <div class="panel-heading">
            <p class="detail-eyebrow">ACCOUNT</p>
            <h2>账号设置</h2>
          </div>
          <div v-if="loading && !user" class="panel-loading">正在加载账号…</div>
          <form v-else class="account-form" @submit.prevent="saveUser">
            <label><span>用户名</span><input v-model="username" class="admin-input" required minlength="1" maxlength="15" pattern="[\u4e00-\u9fa5A-Za-z0-9]{1,15}" /></label>
            <label><span>手机号</span><input v-model="phone" class="admin-input" required type="tel" inputmode="numeric" minlength="11" maxlength="11" pattern="1[3-9][0-9]{9}" /></label>
            <label class="active-toggle"><span><strong>账号启用</strong><small>禁用后该用户无法登录</small></span><input v-model="isActive" type="checkbox" /></label>
            <button class="save-button" type="submit" :disabled="saving">{{ saving ? '保存中…' : '保存更改' }}</button>
          </form>
          <div class="account-facts">
            <div><span>历史会话</span><strong>{{ user?.session_count ?? 0 }}</strong></div>
            <div><span>编辑记录</span><strong>{{ user?.record_count ?? 0 }}</strong></div>
            <div><span>最近活跃</span><strong>{{ formatDate(user?.last_active_at) }}</strong></div>
            <div><span>注册时间</span><strong>{{ formatDate(user?.created_at) }}</strong></div>
          </div>
      </section>

      <section class="history-panel" aria-labelledby="history-title">
          <header class="history-heading">
            <div>
              <p class="detail-eyebrow">ACTIVITY</p>
              <h2 id="history-title">使用记录</h2>
              <p>{{ total }} 个编辑会话</p>
            </div>
            <button class="refresh-link" type="button" :disabled="historyLoading" @click="loadHistory()">
              <svg aria-hidden="true" viewBox="0 0 24 24" fill="none"><path d="M20 11a8 8 0 0 0-14.8-3M4 4v4h4m-4 5a8 8 0 0 0 14.8 3M20 20v-4h-4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>
              刷新
            </button>
          </header>

          <div v-if="historyLoading && sessions.length === 0" class="history-state">正在加载使用记录…</div>
          <div v-else-if="sessions.length === 0" class="history-state">该用户还没有编辑会话。</div>
          <div v-else class="session-list">
            <article v-for="session in sessions" :key="session.id" class="session-row">
              <div class="session-thumb">
                <img v-if="session.last_result_url" :src="session.last_result_url" :alt="session.title || '编辑结果预览'" loading="lazy" />
                <svg v-else aria-hidden="true" viewBox="0 0 24 24" fill="none"><rect x="3" y="4" width="18" height="16" rx="2" stroke="currentColor" stroke-width="1.5"/><circle cx="8.5" cy="9" r="1.5" stroke="currentColor" stroke-width="1.5"/><path d="m4 17 5-5 3 3 3-4 5 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
              </div>
              <div class="session-copy">
                <h3>{{ session.title || '未命名会话' }}</h3>
                <p>{{ session.record_count }} 轮编辑 <span>·</span> {{ formatDate(session.updated_at) }}</p>
              </div>
              <div class="session-actions">
                <button type="button" class="view-session" @click="openSession(session.id)">查看详情 <span aria-hidden="true">›</span></button>
                <button type="button" class="delete-session" @click="removeSession(session.id)">删除</button>
              </div>
            </article>
          </div>

          <nav v-if="!historyLoading && total > pageSize" class="history-pagination" aria-label="使用记录分页">
            <button type="button" :disabled="page === 1" @click="page--; loadHistory()">上一页</button>
            <span>{{ page }} <i>/</i> {{ Math.ceil(total / pageSize) }}</span>
            <button type="button" :disabled="page >= Math.ceil(total / pageSize)" @click="page++; loadHistory()">下一页</button>
          </nav>
      </section>
    </div>

    <Teleport to="body">
      <div v-if="selectedSession" class="session-overlay" @click.self="selectedSession = null">
        <aside class="session-drawer" role="dialog" aria-modal="true" :aria-label="selectedSession.session.title || '会话详情'">
          <header class="drawer-header">
            <div class="drawer-title">
              <p class="detail-eyebrow">SESSION DETAIL</p>
              <h2>{{ selectedSession.session.title || '未命名会话' }}</h2>
              <p>会话 ID：{{ selectedSession.session.id }}</p>
            </div>
            <button class="drawer-close" type="button" aria-label="关闭会话详情" @click="selectedSession = null">×</button>
          </header>
          <div class="drawer-content">
            <article v-for="record in selectedSession.session.records" :key="record.id" class="record-item">
              <div class="record-heading"><span>#{{ record.id }}</span><time>{{ formatDate(record.created_at) }}</time></div>
              <p class="record-instruction">{{ record.instruction }}</p>
              <p class="record-meta">{{ record.provider }} · {{ record.model }} · {{ record.status }}</p>
              <div v-if="record.result_urls?.length" class="record-images">
                <img v-for="url in record.result_urls" :key="url" :src="url" :alt="`编辑记录 ${record.id} 的生成结果`" loading="lazy" />
              </div>
            </article>
            <p v-if="!selectedSession.session.records.length" class="drawer-empty">这个会话还没有编辑记录。</p>
          </div>
        </aside>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.detail-page { min-height: 100vh; padding: 44px 28px 96px; background: #f5f5f7; color: #1d1d1f; }
.detail-shell { max-width: 1180px; margin: 0 auto; }
.detail-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 34px; }
.back-link { display: inline-flex; align-items: center; gap: 5px; margin-bottom: 23px; padding: 0; border: 0; background: transparent; color: #0071e3; font-size: 12px; font-weight: 600; cursor: pointer; }
.back-link span { font-size: 22px; line-height: 12px; }
.detail-eyebrow { color: #86868b; font-size: 10px; font-weight: 700; letter-spacing: 0; margin: 0 0 8px; }
.detail-header h1 { margin: 0; font-size: 42px; line-height: 1.05; letter-spacing: 0; }
.detail-subtitle { margin: 10px 0 0; color: #6e6e73; font-size: 13px; }
.detail-user-mark { display: flex; align-items: center; gap: 11px; padding-bottom: 3px; }
.user-avatar { display: grid; place-items: center; width: 42px; height: 42px; flex: none; border-radius: 8px; background: #1d1d1f; color: white; font-size: 17px; font-weight: 600; }
.detail-user-mark > span:last-child { display: grid; gap: 4px; }
.detail-user-mark strong { font-size: 12px; }
.detail-user-mark small { color: #86868b; font-size: 10px; }
.detail-alert, .detail-success { border-radius: 8px; padding: 11px 13px; font-size: 12px; margin-bottom: 14px; }
.detail-alert { color: #b42318; background: #fff2f0; border: 1px solid #ffd7d2; }
.detail-success { color: #247a45; background: #eef9f1; border: 1px solid #c9eed3; }
.account-panel { display: grid; grid-template-columns: minmax(160px, 220px) minmax(0, 1fr); column-gap: 32px; align-items: start; padding: 22px 0 24px; border-top: 1px solid #d2d2d7; border-bottom: 1px solid #d2d2d7; }
.panel-heading { margin-bottom: 0; }
.panel-heading h2, .history-heading h2 { margin: 0; font-size: 21px; letter-spacing: 0; }
.account-form { display: grid; grid-template-columns: minmax(150px, 1fr) minmax(150px, 1fr) minmax(190px, 1fr) auto; align-items: end; gap: 16px; }
.account-form > label:not(.active-toggle) { display: grid; gap: 7px; }
.account-form > label > span { color: #424245; font-size: 11px; font-weight: 600; }
.admin-input { width: 100%; box-sizing: border-box; height: 41px; padding: 0 12px; border: 1px solid #d2d2d7; border-radius: 8px; background: white; color: #1d1d1f; font-size: 13px; outline: none; }
.admin-input:focus { border-color: #0071e3; box-shadow: 0 0 0 3px rgba(0,113,227,.12); }
.active-toggle { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 11px 0; border-top: 1px solid #e2e2e7; border-bottom: 1px solid #e2e2e7; }
.active-toggle span { display: grid; gap: 4px; }
.active-toggle strong { color: #424245; font-size: 12px; }
.active-toggle small { color: #86868b; font-size: 10px; }
.active-toggle input { width: 16px; height: 16px; accent-color: #0071e3; }
.save-button { justify-self: start; border: 0; border-radius: 999px; padding: 10px 17px; background: #0071e3; color: white; font-size: 12px; font-weight: 600; cursor: pointer; white-space: nowrap; }
.save-button:disabled { opacity: .5; cursor: wait; }
.account-facts { grid-column: 1 / -1; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0; margin-top: 22px; padding-top: 3px; border-top: 1px solid #e2e2e7; }
.account-facts > div { display: flex; justify-content: space-between; gap: 12px; padding: 12px 18px 0 0; }
.account-facts span { flex: none; color: #86868b; font-size: 10px; }
.account-facts strong { color: #424245; font-size: 10px; font-weight: 500; text-align: right; overflow-wrap: anywhere; }
.panel-loading { color: #86868b; padding: 28px 0; font-size: 12px; }
.history-panel { min-width: 0; margin-top: 30px; }
.history-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding-bottom: 18px; border-bottom: 1px solid #d2d2d7; }
.history-heading > div > p:last-child { margin: 7px 0 0; color: #86868b; font-size: 11px; }
.refresh-link { display: inline-flex; align-items: center; gap: 5px; border: 0; background: transparent; color: #0071e3; font-size: 11px; cursor: pointer; }
.refresh-link svg { width: 14px; height: 14px; }
.refresh-link:disabled { opacity: .5; cursor: wait; }
.history-state { color: #86868b; padding: 54px 10px; text-align: center; font-size: 12px; }
.session-row { display: grid; grid-template-columns: 92px minmax(0, 1fr) auto; align-items: center; gap: 16px; padding: 17px 0; border-bottom: 1px solid #e2e2e7; }
.session-thumb { display: grid; place-items: center; overflow: hidden; width: 92px; aspect-ratio: 4 / 3; border-radius: 8px; background: #e9e9ed; color: #a1a1a6; }
.session-thumb img { display: block; width: 100%; height: 100%; object-fit: cover; }
.session-thumb svg { width: 26px; height: 26px; }
.session-copy { min-width: 0; }
.session-copy h3 { margin: 0; overflow: hidden; color: #1d1d1f; font-size: 13px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.session-copy p { margin: 6px 0 0; color: #86868b; font-size: 10px; }
.session-copy p span { margin: 0 4px; }
.session-actions { display: flex; align-items: center; gap: 12px; }
.view-session, .delete-session { border: 0; background: transparent; cursor: pointer; white-space: nowrap; }
.view-session { color: #0071e3; font-size: 11px; font-weight: 600; }
.view-session span { margin-left: 2px; font-size: 18px; vertical-align: -1px; }
.delete-session { color: #86868b; font-size: 10px; }
.delete-session:hover { color: #c43d32; }
.history-pagination { display: flex; justify-content: center; align-items: center; gap: 18px; padding: 19px 0; }
.history-pagination button { border: 0; background: transparent; color: #0071e3; font-size: 11px; cursor: pointer; }
.history-pagination button:disabled { color: #b8b8bd; cursor: not-allowed; }
.history-pagination span { color: #424245; font-size: 11px; }
.history-pagination i { color: #a1a1a6; font-style: normal; margin: 0 5px; }
.session-overlay { position: fixed; z-index: 60; inset: 0; display: flex; justify-content: flex-end; background: rgb(16 18 22 / 34%); backdrop-filter: blur(3px); }
.session-drawer { display: flex; flex-direction: column; width: min(620px, 92vw); height: 100%; background: #f5f5f7; color: #1d1d1f; box-shadow: -18px 0 55px rgb(0 0 0 / 14%); animation: drawer-in .22s ease-out; }
.drawer-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; padding: 30px 30px 22px; border-bottom: 1px solid #d2d2d7; background: rgb(255 255 255 / 86%); }
.drawer-title { min-width: 0; }
.drawer-title h2 { margin: 0; overflow-wrap: anywhere; font-size: 22px; letter-spacing: 0; }
.drawer-title > p:last-child { margin: 8px 0 0; color: #86868b; font-size: 11px; }
.drawer-close { display: grid; place-items: center; flex: none; width: 34px; height: 34px; border: 0; border-radius: 50%; background: #ededf0; color: #424245; font-size: 24px; line-height: 1; cursor: pointer; }
.drawer-content { flex: 1; overflow-y: auto; padding: 22px 24px 40px; }
.record-item { margin-bottom: 14px; padding: 18px; border: 1px solid #e2e2e7; border-radius: 8px; background: white; }
.record-heading { display: flex; justify-content: space-between; gap: 14px; color: #86868b; font-size: 10px; }
.record-heading > span { color: #0071e3; font-weight: 700; }
.record-heading time { text-align: right; }
.record-instruction { margin: 12px 0 7px; color: #1d1d1f; font-size: 13px; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
.record-meta { margin: 0; color: #86868b; font-size: 10px; overflow-wrap: anywhere; }
.record-images { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 14px; }
.record-images img { display: block; width: 100%; aspect-ratio: 4 / 3; border-radius: 8px; background: #f5f5f7; object-fit: cover; }
.drawer-empty { padding: 44px 10px; color: #86868b; text-align: center; font-size: 13px; }
@keyframes drawer-in { from { transform: translateX(24px); opacity: .7; } to { transform: translateX(0); opacity: 1; } }
@media (max-width: 820px) {
  .detail-page { padding: 32px 18px 90px; }
  .detail-header h1 { font-size: 36px; }
  .account-panel { grid-template-columns: 1fr; row-gap: 20px; }
  .account-form { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .account-facts { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 560px) {
  .detail-page { padding: 26px 15px 86px; }
  .detail-header { align-items: flex-start; flex-direction: column; margin-bottom: 26px; }
  .detail-user-mark { display: none; }
  .account-form { grid-template-columns: 1fr; }
  .account-facts > div { display: grid; gap: 5px; padding-right: 8px; }
  .account-facts strong { text-align: left; }
  .session-row { grid-template-columns: 70px minmax(0, 1fr); gap: 11px; }
  .session-thumb { width: 70px; }
  .session-actions { grid-column: 2; justify-content: space-between; }
  .session-drawer { width: 100%; }
  .drawer-header { padding: 22px 18px 18px; }
  .drawer-content { padding: 16px 14px 30px; }
  .record-item { padding: 15px; }
}
@media (prefers-reduced-motion: reduce) { .session-drawer { animation: none; } }
</style>
