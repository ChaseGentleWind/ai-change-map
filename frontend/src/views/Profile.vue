<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { updatePassword } from '@/api'
import { useAuth } from '@/stores/auth'

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

const userInitial = computed(() => auth.state.user?.username?.slice(0, 1).toUpperCase() || 'U')
const createdAt = computed(() => {
  if (!auth.state.user?.created_at) return '暂无'
  return new Date(auth.state.user.created_at).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
})

watch(
  () => auth.state.user,
  user => {
    username.value = user?.username || ''
    phone.value = user?.phone || ''
  },
  { immediate: true }
)

async function submitProfile() {
  if (profileLoading.value) return
  profileError.value = ''
  profileMessage.value = ''
  profileLoading.value = true

  try {
    await auth.updateProfile({
      username: username.value.trim(),
      phone: phone.value.trim()
    })
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
    await updatePassword({
      current_password: currentPassword.value,
      new_password: newPassword.value
    })
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
  <div class="min-h-screen px-4 py-5 sm:px-6 sm:py-8 lg:px-8">
    <div class="mx-auto max-w-5xl">
      <header class="mb-5 sm:mb-6">
        <p class="text-[12px] font-medium text-ink-muted mb-1">账号设置</p>
        <h1 class="text-[24px] sm:text-[28px] font-semibold text-ink leading-tight">个人中心</h1>
      </header>

      <section class="mb-5 rounded-card border border-line bg-white p-4 sm:p-5">
        <div class="flex items-center gap-3">
          <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-brand text-lg font-semibold text-white">
            {{ userInitial }}
          </div>
          <div class="min-w-0">
            <p class="truncate text-[16px] font-semibold text-ink">{{ auth.state.user?.username || '未命名用户' }}</p>
            <p class="text-[13px] text-ink-muted">{{ auth.state.user?.phone || '未绑定手机号' }}</p>
          </div>
        </div>
        <div class="mt-4 grid gap-3 text-[13px] text-ink-soft sm:grid-cols-2">
          <div class="rounded-lg bg-canvas px-3 py-2">
            <span class="text-ink-muted">账号 ID</span>
            <span class="ml-2 font-medium text-ink">{{ auth.state.user?.id }}</span>
          </div>
          <div class="rounded-lg bg-canvas px-3 py-2">
            <span class="text-ink-muted">注册时间</span>
            <span class="ml-2 font-medium text-ink">{{ createdAt }}</span>
          </div>
        </div>
      </section>

      <div class="grid gap-5 lg:grid-cols-2">
        <section class="rounded-card border border-line bg-white p-4 shadow-hover sm:p-5">
          <div class="mb-4">
            <h2 class="text-[18px] font-semibold text-ink">基础资料</h2>
            <p class="mt-1 text-[13px] text-ink-muted">用户名和手机号会用于登录与账号识别。</p>
          </div>

          <form class="space-y-4" @submit.prevent="submitProfile">
            <label class="block">
              <span class="block text-[13px] font-medium text-ink-soft mb-1.5">用户名</span>
              <input
                v-model="username"
                class="dk-input rounded-lg"
                required
                minlength="1"
                maxlength="15"
                pattern="[\u4e00-\u9fa5A-Za-z0-9]{1,15}"
                autocomplete="username"
                placeholder="中文、字母或数字，1-15 位"
              />
            </label>

            <label class="block">
              <span class="block text-[13px] font-medium text-ink-soft mb-1.5">手机号</span>
              <input
                v-model="phone"
                class="dk-input rounded-lg"
                required
                type="tel"
                inputmode="numeric"
                minlength="11"
                maxlength="11"
                pattern="1[3-9][0-9]{9}"
                autocomplete="tel"
                placeholder="请输入 11 位手机号"
              />
            </label>

            <div v-if="profileError" class="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-600">
              {{ profileError }}
            </div>
            <div v-if="profileMessage" class="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-[13px] text-green-700">
              {{ profileMessage }}
            </div>

            <button type="submit" class="dk-btn-primary w-full rounded-lg py-3" :disabled="profileLoading">
              {{ profileLoading ? '保存中...' : '保存资料' }}
            </button>
          </form>
        </section>

        <section class="rounded-card border border-line bg-white p-4 shadow-hover sm:p-5">
          <div class="mb-4">
            <h2 class="text-[18px] font-semibold text-ink">修改密码</h2>
            <p class="mt-1 text-[13px] text-ink-muted">修改密码需要先输入当前密码。</p>
          </div>

          <form class="space-y-4" @submit.prevent="submitPassword">
            <label class="block">
              <span class="block text-[13px] font-medium text-ink-soft mb-1.5">当前密码</span>
              <input
                v-model="currentPassword"
                class="dk-input rounded-lg"
                required
                type="password"
                autocomplete="current-password"
                placeholder="请输入当前密码"
              />
            </label>

            <label class="block">
              <span class="block text-[13px] font-medium text-ink-soft mb-1.5">新密码</span>
              <input
                v-model="newPassword"
                class="dk-input rounded-lg"
                required
                type="password"
                minlength="6"
                maxlength="128"
                autocomplete="new-password"
                placeholder="至少 6 个字符"
              />
            </label>

            <label class="block">
              <span class="block text-[13px] font-medium text-ink-soft mb-1.5">确认新密码</span>
              <input
                v-model="confirmPassword"
                class="dk-input rounded-lg"
                required
                type="password"
                minlength="6"
                maxlength="128"
                autocomplete="new-password"
                placeholder="再次输入新密码"
              />
            </label>

            <div v-if="passwordError" class="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-600">
              {{ passwordError }}
            </div>
            <div v-if="passwordMessage" class="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-[13px] text-green-700">
              {{ passwordMessage }}
            </div>

            <button type="submit" class="dk-btn-primary w-full rounded-lg py-3" :disabled="passwordLoading">
              {{ passwordLoading ? '更新中...' : '更新密码' }}
            </button>
          </form>
        </section>
      </div>
    </div>
  </div>
</template>
