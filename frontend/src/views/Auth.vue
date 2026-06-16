<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuth()

const username = ref('')
const phone = ref('')
const account = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

const mode = computed(() => route.meta.authMode === 'register' ? 'register' : 'login')
const isRegister = computed(() => mode.value === 'register')
const title = computed(() => isRegister.value ? '创建账号' : '登录账号')
const submitText = computed(() => isRegister.value ? '注册并进入' : '登录')
const switchText = computed(() => isRegister.value ? '已有账号？去登录' : '没有账号？去注册')
const switchPath = computed(() => isRegister.value ? '/login' : '/register')

async function submit() {
  if (loading.value) return

  error.value = ''
  loading.value = true

  try {
    if (isRegister.value) {
      await auth.register({
        username: username.value.trim(),
        phone: phone.value.trim(),
        password: password.value
      })
    } else {
      await auth.login({
        username_or_phone: account.value.trim(),
        password: password.value
      })
    }

    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.replace(redirect)
  } catch (e: any) {
    error.value = e.message || '操作失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-canvas flex items-center justify-center px-5 py-8 sm:px-6 sm:py-10">
    <div class="w-full max-w-[920px] grid gap-6 md:grid-cols-[1fr_420px] md:gap-8 md:items-center">
      <section class="hidden md:block">
        <div class="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-brand text-white font-bold text-lg mb-5">
          AI
        </div>
        <h1 class="text-[28px] font-semibold text-ink leading-tight mb-3">AI 商品图精细编辑</h1>
        <p class="text-[14px] text-ink-muted leading-7 max-w-md">
          登录后保存你的编辑会话、历史记录和多轮结果，每个账号的数据独立可见。
        </p>
      </section>

      <section class="dk-card bg-white border border-line p-5 shadow-hover sm:p-6">
        <div class="mb-6">
          <h2 class="text-[22px] font-semibold text-ink">{{ title }}</h2>
          <p class="text-[13px] text-ink-muted mt-1">使用账号继续编辑你的图片项目</p>
        </div>

        <form class="space-y-4" @submit.prevent="submit">
          <label v-if="isRegister" class="block">
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

          <label v-if="isRegister" class="block">
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

          <label v-else class="block">
            <span class="block text-[13px] font-medium text-ink-soft mb-1.5">用户名或手机号</span>
            <input
              v-model="account"
              class="dk-input rounded-lg"
              required
              autocomplete="username"
              placeholder="请输入用户名或手机号"
            />
          </label>

          <label class="block">
            <span class="block text-[13px] font-medium text-ink-soft mb-1.5">密码</span>
            <input
              v-model="password"
              class="dk-input rounded-lg"
              required
              type="password"
              :minlength="isRegister ? 6 : 1"
              maxlength="128"
              :autocomplete="isRegister ? 'new-password' : 'current-password'"
              placeholder="请输入密码"
            />
          </label>

          <div v-if="error" class="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-600">
            {{ error }}
          </div>

          <button
            type="submit"
            class="w-full dk-btn-primary py-3 rounded-lg"
            :disabled="loading"
          >
            <svg v-if="loading" class="animate-spin h-4 w-4 mr-2" viewBox="0 0 24 24" fill="none">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            {{ loading ? '处理中...' : submitText }}
          </button>
        </form>

        <router-link
          class="mt-5 inline-flex w-full items-center justify-center text-[13px] font-medium text-brand hover:underline"
          :to="{ path: switchPath, query: route.query }"
        >
          {{ switchText }}
        </router-link>
      </section>
    </div>
  </div>
</template>
