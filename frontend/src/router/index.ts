// Vue Router 配置
import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/Home.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/history',
      name: 'history',
      component: () => import('@/views/History.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/profile',
      name: 'profile',
      component: () => import('@/views/Profile.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/admin/users',
      name: 'admin-users',
      component: () => import('@/views/AdminUsers.vue'),
      meta: { requiresAuth: true, requiresAdmin: true }
    },
    {
      path: '/admin/users/:userId',
      name: 'admin-user-detail',
      component: () => import('@/views/AdminUserDetail.vue'),
      meta: { requiresAuth: true, requiresAdmin: true }
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/Auth.vue'),
      meta: { guestOnly: true, authMode: 'login' }
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/Auth.vue'),
      meta: { guestOnly: true, authMode: 'register' }
    }
  ]
})

router.beforeEach(async (to) => {
  const auth = useAuth()
  await auth.initAuth()

  if (to.meta.requiresAuth && !auth.isAuthenticated.value) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  if (to.meta.requiresAdmin && !auth.state.user?.is_admin) {
    return '/'
  }

  if (to.meta.guestOnly && auth.isAuthenticated.value) {
    const redirect = typeof to.query.redirect === 'string' ? to.query.redirect : '/'
    return redirect
  }
})

export default router
