<script setup lang="ts">
import { RouterView, useRoute, useRouter } from 'vue-router'
import { computed } from 'vue'
import { useAuth } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuth()

const navItems = computed(() => {
  const items = [
    { to: '/', label: '编辑', icon: 'edit' },
    { to: '/history', label: '历史', icon: 'history' },
    { to: '/profile', label: '我的', icon: 'user' }
  ]

  if (auth.state.user?.is_admin) {
    items.push({ to: '/admin/users', label: '管理', icon: 'admin' })
  }

  return items
})

const activePath = computed(() => route.path)
const isAuthPage = computed(() => route.path === '/login' || route.path === '/register')
const userInitial = computed(() => auth.state.user?.username?.slice(0, 1).toUpperCase() || 'U')
const userTitle = computed(() => auth.state.user?.phone || auth.state.user?.username || '当前用户')

async function handleLogout() {
  auth.logout()
  await router.replace('/login')
}
</script>

<template>
  <RouterView v-if="isAuthPage" />

  <div v-else class="min-h-screen bg-canvas text-ink md:flex">
    <aside class="fixed inset-x-0 bottom-0 z-30 h-16 bg-sidebar border-t border-line/60 flex items-center justify-between px-3 md:sticky md:inset-auto md:top-0 md:h-screen md:w-20 md:shrink-0 md:flex-col md:justify-start md:border-t-0 md:px-0 md:py-4">
      <router-link to="/" class="hidden md:flex w-10 h-10 rounded-xl bg-brand text-white items-center justify-center font-bold text-lg mb-6">
        AI
      </router-link>

      <nav class="flex flex-1 items-center justify-center gap-1 md:flex-none md:flex-col md:gap-1 md:w-16">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="flex h-12 w-14 flex-col items-center justify-center rounded-xl transition-colors sm:w-16 md:h-16"
          :class="activePath === item.to ? 'bg-selected text-ink' : 'text-ink-soft hover:bg-selected/60'"
        >
          <svg v-if="item.icon === 'edit'" class="mb-1 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.8">
            <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125" />
          </svg>
          <svg v-else-if="item.icon === 'history'" class="mb-1 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.8">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
          </svg>
          <svg v-else-if="item.icon === 'user'" class="mb-1 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.8">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 7.5a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
          </svg>
          <svg v-else class="mb-1 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.8">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.75c0 5.592 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.75A11.959 11.959 0 0 1 12 2.714Z" />
          </svg>
          <span class="text-[12px]">{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="flex items-center gap-1.5 md:mt-auto md:flex-col md:gap-2">
        <router-link
          to="/profile"
          class="hidden h-10 w-10 items-center justify-center rounded-xl border border-line bg-white text-[13px] font-semibold text-ink sm:flex"
          :title="userTitle"
        >
          {{ userInitial }}
        </router-link>
        <button
          class="flex h-10 w-10 items-center justify-center rounded-xl text-ink-muted transition-colors hover:bg-selected hover:text-red-500"
          title="退出登录"
          @click="handleLogout"
        >
          <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.8">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6A2.25 2.25 0 0 0 5.25 5.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9" />
          </svg>
        </button>
      </div>
    </aside>

    <main class="min-w-0 pb-20 md:flex-1 md:pb-0">
      <RouterView />
    </main>
  </div>
</template>
