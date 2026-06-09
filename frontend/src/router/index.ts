// Vue Router 配置
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/Home.vue')
    },
    {
      path: '/history',
      name: 'history',
      component: () => import('@/views/History.vue')
    }
  ]
})

export default router
