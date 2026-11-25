import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

export const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: { requiresAuth: true, title: 'Мои заказы' },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { guestOnly: true, title: 'Вход' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: 'Страница не найдена' },
  },
]

// Возврат после входа только на внутренние пути: ?redirect=//evil.example — не открытый редирект
export function safeRedirect(value) {
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') ? value : '/'
}

export function createAppRouter(history = createWebHistory(import.meta.env.BASE_URL)) {
  const router = createRouter({ history, routes })

  // meta.requiresAuth — лишь пометка; проверяет её этот guard перед каждым переходом
  router.beforeEach(async (to) => {
    const auth = useAuthStore()
    if (to.meta.requiresAuth && !auth.isAuthenticated) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }
    if (to.meta.guestOnly && auth.isAuthenticated) {
      return { name: 'home' }
    }
    if (auth.isAuthenticated && !auth.user) {
      try {
        await auth.fetchMe() // после перезагрузки страницы восстанавливаем имя и роль
      } catch {
        // 401 обработает interceptor; сетевую ошибку покажет экран
      }
    }
    return true
  })

  router.afterEach((to) => {
    document.title = `${to.meta.title ?? 'Ресторан'} · Ресторан «Пряность»`
  })

  return router
}

export default createAppRouter()
