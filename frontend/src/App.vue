<script setup lang="ts">
import { RouterView, useRoute, useRouter } from 'vue-router'
import { computed } from 'vue'
import { useAuth } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuth()

const navItems = [
  { to: '/', label: '编辑', icon: 'edit' },
  { to: '/history', label: '历史', icon: 'history' },
]

const activePath = computed(() => route.path)
const isAuthPage = computed(() => route.path === '/login' || route.path === '/register')

async function handleLogout() {
  auth.logout()
  await router.replace('/login')
}
</script>

<template>
  <RouterView v-if="isAuthPage" />

  <div v-else class="min-h-screen flex bg-canvas text-ink">
    <!-- 左侧 80px 窄边栏 -->
    <aside class="w-20 shrink-0 bg-sidebar flex flex-col items-center py-4 sticky top-0 h-screen">
      <!-- Logo -->
      <router-link to="/" class="w-10 h-10 rounded-xl bg-brand text-white flex items-center justify-center font-bold text-lg mb-6">
        AI
      </router-link>

      <!-- 导航项 -->
      <nav class="flex flex-col gap-1 w-16">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="flex flex-col items-center justify-center h-16 rounded-xl transition-colors"
          :class="activePath === item.to ? 'bg-selected text-ink' : 'text-ink-soft hover:bg-selected/60'"
        >
          <!-- icons -->
          <svg v-if="item.icon === 'edit'" class="w-5 h-5 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.8">
            <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125"/>
          </svg>
          <svg v-else-if="item.icon === 'history'" class="w-5 h-5 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.8">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"/>
          </svg>
          <span class="text-[12px]">{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="mt-auto flex flex-col items-center gap-2">
        <div
          class="w-10 h-10 rounded-xl bg-white border border-line flex items-center justify-center text-[13px] font-semibold text-ink"
          :title="auth.state.user?.email || auth.state.user?.username"
        >
          {{ auth.state.user?.username?.slice(0, 1).toUpperCase() || 'U' }}
        </div>
        <button
          class="w-10 h-10 rounded-xl text-ink-muted hover:text-red-500 hover:bg-selected transition-colors flex items-center justify-center"
          title="退出登录"
          @click="handleLogout"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.8">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6A2.25 2.25 0 0 0 5.25 5.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9"/>
          </svg>
        </button>
      </div>
    </aside>

    <!-- 右侧主区 -->
    <main class="flex-1 min-w-0">
      <RouterView />
    </main>
  </div>
</template>
