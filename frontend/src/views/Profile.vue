<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { getUsageSummary, updatePassword } from '@/api'
import { useAuth } from '@/stores/auth'
import type { UsageSummary } from '@/types'

const auth = useAuth()
const username = ref('')
const phone = ref('')
const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const profileLoading = ref(false)
const passwordLoading = ref(false)
const profileError = ref('')
const passwordError = ref('')
const profileMessage = ref('')
const passwordMessage = ref('')
const usagePeriod = ref<'today' | 'all'>('today')
const usage = ref<UsageSummary | null>(null)
const usageLoading = ref(false)
const usageError = ref('')

const userInitial = computed(() => auth.state.user?.username?.slice(0, 1).toUpperCase() || 'U')
const createdAt = computed(() => {
  if (!auth.state.user?.created_at) return '暂无'
  return new Date(auth.state.user.created_at).toLocaleDateString('zh-CN', {
    year: 'numeric', month: 'long', day: 'numeric'
  })
})

watch(() => auth.state.user, user => {
  username.value = user?.username || ''
  phone.value = user?.phone || ''
}, { immediate: true })
watch(usagePeriod, loadUsage)
onMounted(loadUsage)

async function loadUsage() {
  usageLoading.value = true
  usageError.value = ''
  try {
    usage.value = await getUsageSummary(usagePeriod.value)
  } catch (e: any) {
    usageError.value = e.message || '费用统计暂时无法加载'
  } finally {
    usageLoading.value = false
  }
}

async function submitProfile() {
  if (profileLoading.value) return
  profileError.value = ''
  profileMessage.value = ''
  profileLoading.value = true
  try {
    await auth.updateProfile({ username: username.value.trim(), phone: phone.value.trim() })
    profileMessage.value = '资料已保存'
  } catch (e: any) {
    profileError.value = e.message || '保存失败，请重试'
  } finally {
    profileLoading.value = false
  }
}

async function submitPassword() {
  if (passwordLoading.value) return
  passwordError.value = ''
  passwordMessage.value = ''
  if (newPassword.value !== confirmPassword.value) {
    passwordError.value = '两次输入的新密码不一致'
    return
  }
  passwordLoading.value = true
  try {
    await updatePassword({ current_password: currentPassword.value, new_password: newPassword.value })
    currentPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
    passwordMessage.value = '密码已更新'
  } catch (e: any) {
    passwordError.value = e.message || '密码更新失败，请重试'
  } finally {
    passwordLoading.value = false
  }
}
</script>

<template>
  <div class="account-page">
    <div class="account-shell">
      <header class="account-header">
        <div>
          <p class="account-eyebrow">ACCOUNT</p>
          <h1>个人中心</h1>
          <p class="account-lede">管理你的账号资料、安全设置和图像生成用量。</p>
        </div>
        <router-link to="/" class="account-action">开始编辑 <span aria-hidden="true">↗</span></router-link>
      </header>

      <section class="profile-hero" aria-label="账号概览">
        <div class="profile-avatar">{{ userInitial }}</div>
        <div class="profile-identity">
          <div class="profile-name-row">
            <h2>{{ auth.state.user?.username || '未命名用户' }}</h2>
            <span class="status-pill">正常使用</span>
          </div>
          <p>{{ auth.state.user?.phone || '未绑定手机号' }}</p>
          <div class="profile-meta">
            <span>账号 ID {{ auth.state.user?.id }}</span>
            <span>加入于 {{ createdAt }}</span>
          </div>
        </div>
      </section>

      <section class="usage-strip" aria-labelledby="usage-title">
        <div class="usage-heading">
          <div>
            <p class="section-kicker">USAGE</p>
            <h2 id="usage-title">图像生成用量</h2>
          </div>
          <div class="period-switch" role="group" aria-label="费用统计范围">
            <button type="button" :class="{ active: usagePeriod === 'today' }" :aria-pressed="usagePeriod === 'today'" @click="usagePeriod = 'today'">今日</button>
            <button type="button" :class="{ active: usagePeriod === 'all' }" :aria-pressed="usagePeriod === 'all'" @click="usagePeriod = 'all'">累计</button>
          </div>
        </div>
        <div v-if="usageLoading && !usage" class="usage-state">正在加载费用统计…</div>
        <div v-else-if="usageError" class="inline-error" role="alert">{{ usageError }}</div>
        <template v-else-if="usage">
          <div class="usage-metrics">
            <div><span>{{ usagePeriod === 'today' ? '今日费用' : '累计费用' }}</span><strong>¥{{ usage.cost.toFixed(2) }}</strong></div>
            <div><span>成功生成</span><strong>{{ usage.image_count }} <small>张</small></strong></div>
            <div><span>使用模型</span><strong>{{ usage.models.length }} <small>种</small></strong></div>
          </div>
          <div v-if="usage.models.length" class="model-breakdown">
            <div v-for="item in usage.models" :key="item.model" class="model-row">
              <span>{{ item.model }} <em>¥{{ item.unit_price.toFixed(2) }} / 张</em></span>
              <span>{{ item.image_count }} 张 · ¥{{ item.cost.toFixed(2) }}</span>
            </div>
          </div>
          <p v-else class="usage-empty">{{ usagePeriod === 'today' ? '今天还没有成功生成图片' : '暂无费用记录' }}</p>
          <p class="usage-note">费用按模型标注单价估算，最终以 API 账单为准。</p>
        </template>
      </section>

      <div class="settings-grid">
        <section class="settings-section">
          <div class="section-heading">
            <p class="section-kicker">PROFILE</p>
            <h2>基础资料</h2>
            <p>更新你的公开身份信息。</p>
          </div>
          <form class="settings-form" @submit.prevent="submitProfile">
            <label><span>用户名</span><input v-model="username" class="apple-input" required minlength="1" maxlength="15" pattern="[\u4e00-\u9fa5A-Za-z0-9]{1,15}" autocomplete="username" /></label>
            <label><span>手机号</span><input v-model="phone" class="apple-input" required type="tel" inputmode="numeric" minlength="11" maxlength="11" pattern="1[3-9][0-9]{9}" autocomplete="tel" /></label>
            <div v-if="profileError" class="inline-error">{{ profileError }}</div>
            <div v-if="profileMessage" class="inline-success">{{ profileMessage }}</div>
            <button type="submit" class="apple-button" :disabled="profileLoading">{{ profileLoading ? '保存中…' : '保存资料' }}</button>
          </form>
        </section>

        <section class="settings-section">
          <div class="section-heading">
            <p class="section-kicker">SECURITY</p>
            <h2>修改密码</h2>
            <p>定期更新密码，保护你的账号安全。</p>
          </div>
          <form class="settings-form" @submit.prevent="submitPassword">
            <label><span>当前密码</span><input v-model="currentPassword" class="apple-input" required type="password" autocomplete="current-password" /></label>
            <label><span>新密码</span><input v-model="newPassword" class="apple-input" required type="password" minlength="6" maxlength="128" autocomplete="new-password" /></label>
            <label><span>确认新密码</span><input v-model="confirmPassword" class="apple-input" required type="password" minlength="6" maxlength="128" autocomplete="new-password" /></label>
            <div v-if="passwordError" class="inline-error">{{ passwordError }}</div>
            <div v-if="passwordMessage" class="inline-success">{{ passwordMessage }}</div>
            <button type="submit" class="apple-button" :disabled="passwordLoading">{{ passwordLoading ? '更新中…' : '更新密码' }}</button>
          </form>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.account-page { min-height: 100vh; background: #f5f5f7; color: #1d1d1f; padding: 52px 28px 96px; }
.account-shell { max-width: 1080px; margin: 0 auto; }
.account-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 42px; }
.account-eyebrow, .section-kicker { color: #86868b; font-size: 11px; font-weight: 700; letter-spacing: 0; margin: 0 0 10px; }
.account-header h1 { font-size: 48px; line-height: 1.04; letter-spacing: 0; margin: 0; font-weight: 700; }
.account-lede { color: #6e6e73; font-size: 15px; margin: 14px 0 0; }
.account-action { color: #0071e3; font-size: 14px; font-weight: 600; text-decoration: none; white-space: nowrap; }
.account-action span { margin-left: 4px; }
.profile-hero { display: flex; align-items: center; gap: 22px; padding: 27px 0; border-top: 1px solid #d2d2d7; border-bottom: 1px solid #d2d2d7; }
.profile-avatar { display: grid; place-items: center; width: 76px; height: 76px; border-radius: 18px; background: #1d1d1f; color: white; font-size: 31px; font-weight: 650; }
.profile-identity { min-width: 0; }
.profile-name-row { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.profile-name-row h2 { font-size: 24px; letter-spacing: 0; margin: 0; }
.profile-identity > p { color: #6e6e73; margin: 5px 0 0; font-size: 14px; }
.profile-meta { display: flex; flex-wrap: wrap; gap: 16px; color: #86868b; font-size: 12px; margin-top: 13px; }
.status-pill { color: #247a45; background: #e9f7ee; border-radius: 999px; padding: 5px 9px; font-size: 11px; font-weight: 600; }
.usage-strip { padding: 35px 0 30px; border-bottom: 1px solid #d2d2d7; }
.usage-heading { display: flex; justify-content: space-between; gap: 24px; }
.usage-heading h2, .section-heading h2 { font-size: 21px; letter-spacing: 0; margin: 0; }
.period-switch { align-self: flex-start; display: inline-flex; gap: 3px; border: 1px solid #d2d2d7; border-radius: 999px; padding: 3px; background: #fff; }
.period-switch button { border: 0; border-radius: 999px; background: transparent; color: #6e6e73; font-size: 12px; padding: 6px 12px; cursor: pointer; }
.period-switch button.active { background: #1d1d1f; color: #fff; }
.usage-metrics { display: grid; grid-template-columns: repeat(3, 1fr); margin: 30px 0 24px; }
.usage-metrics > div { padding: 0 24px; border-left: 1px solid #d2d2d7; }
.usage-metrics > div:first-child { padding-left: 0; border-left: 0; }
.usage-metrics span { display: block; color: #6e6e73; font-size: 12px; margin-bottom: 7px; }
.usage-metrics strong { font-size: 27px; letter-spacing: 0; font-weight: 650; }
.usage-metrics small { color: #6e6e73; font-size: 12px; font-weight: 400; }
.model-breakdown { border-top: 1px solid #e8e8ed; }
.model-row { display: flex; justify-content: space-between; gap: 20px; padding: 13px 0; color: #424245; font-size: 12px; border-bottom: 1px solid #e8e8ed; }
.model-row em { color: #86868b; font-style: normal; margin-left: 6px; }
.model-row > span:last-child { color: #6e6e73; white-space: nowrap; }
.usage-note, .usage-empty { color: #86868b; font-size: 11px; margin: 14px 0 0; }
.usage-state { color: #6e6e73; font-size: 13px; padding: 36px 0; }
.settings-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 72px; padding-top: 42px; }
.section-heading { margin-bottom: 25px; }
.section-heading h2 { font-size: 22px; }
.section-heading > p:last-child { color: #6e6e73; font-size: 13px; margin: 8px 0 0; }
.settings-form { display: grid; gap: 17px; }
.settings-form label { display: grid; gap: 8px; }
.settings-form label > span { color: #424245; font-size: 12px; font-weight: 600; }
.apple-input { width: 100%; box-sizing: border-box; padding: 12px 14px; border: 1px solid #d2d2d7; border-radius: 8px; background: #fff; color: #1d1d1f; font-size: 14px; outline: none; transition: border-color .2s, box-shadow .2s; }
.apple-input:focus { border-color: #0071e3; box-shadow: 0 0 0 3px rgba(0,113,227,.14); }
.apple-button { border: 0; border-radius: 999px; background: #0071e3; color: #fff; font-size: 13px; font-weight: 600; padding: 11px 18px; cursor: pointer; justify-self: start; min-width: 116px; }
.apple-button:disabled { opacity: .5; cursor: not-allowed; }
.inline-error, .inline-success { border-radius: 8px; padding: 10px 12px; font-size: 12px; }
.inline-error { color: #b42318; background: #fff2f0; border: 1px solid #ffd7d2; }
.inline-success { color: #247a45; background: #eef9f1; border: 1px solid #c9eed3; }
@media (max-width: 720px) {
  .account-page { padding: 32px 18px 88px; }
  .account-header h1 { font-size: 36px; }
  .account-header { align-items: flex-start; flex-direction: column; margin-bottom: 32px; }
  .profile-hero { align-items: flex-start; }
  .usage-heading { align-items: flex-start; flex-direction: column; }
  .usage-metrics { gap: 16px 0; grid-template-columns: repeat(2, 1fr); }
  .usage-metrics > div:nth-child(3) { border-left: 0; padding-left: 0; }
  .settings-grid { display: block; padding-top: 34px; }
  .settings-section + .settings-section { margin-top: 48px; }
  .model-row { align-items: flex-start; flex-direction: column; gap: 5px; }
}
</style>
