import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

export const routes = [
  {
    // Гость видит лендинг, вошедший пользователь — меню (RootView выбирает экран)
    path: '/',
    name: 'home',
    component: () => import('@/views/RootView.vue'),
    meta: { title: 'Главная' },
  },
  {
    path: '/orders',
    name: 'orders',
    component: () => import('@/views/OrdersView.vue'),
    meta: { requiresAuth: true, title: 'Заказы' },
  },
  // /dishes/create раньше /dishes/:id, а :id принимает только цифры
  {
    path: '/dishes/create',
    name: 'dish-create',
    component: () => import('@/views/DishCreateView.vue'),
    meta: { requiresAuth: true, requiresStaff: true, title: 'Новое блюдо' },
  },
  {
    path: '/dishes/:id(\\d+)',
    name: 'dish-detail',
    component: () => import('@/views/DishDetailView.vue'),
    props: true,
    meta: { requiresAuth: true, title: 'Блюдо' },
  },
  {
    path: '/dishes/:id(\\d+)/edit',
    name: 'dish-edit',
    component: () => import('@/views/DishEditView.vue'),
    props: true,
    meta: { requiresAuth: true, requiresStaff: true, title: 'Редактирование блюда' },
  },
  {
    path: '/account',
    name: 'account',
    component: () => import('@/views/AccountView.vue'),
    meta: { requiresAuth: true, title: 'Аккаунт' },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { guestOnly: true, title: 'Вход' },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/RegisterView.vue'),
    meta: { guestOnly: true, title: 'Регистрация' },
  },
  {
    path: '/verify-email',
    name: 'verify-email',
    component: () => import('@/views/VerifyEmailView.vue'),
    meta: { title: 'Подтверждение email' },
  },
  {
    path: '/verify-age',
    name: 'verify-age',
    component: () => import('@/views/VerifyAgeView.vue'),
    meta: { title: 'Подтверждение возраста' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: 'Страница не найдена' },
  },
]

export function safeRedirect(value) {
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') ? value : '/'
}

export function createAppRouter(history = createWebHistory(import.meta.env.BASE_URL)) {
  const router = createRouter({ history, routes })

  router.beforeEach(async (to) => {
    const auth = useAuthStore()
    await auth.init() // сессия в cookie: узнаём о ней один раз, через /auth/me
    if (to.meta.requiresAuth && !auth.isAuthenticated) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }
    if (to.meta.guestOnly && auth.isAuthenticated) {
      return { name: 'home' }
    }
    // Интерфейс лишь не предлагает недоступное; права проверяет бэкенд (403)
    if (to.meta.requiresStaff && !auth.isStaff) {
      return { name: 'home' }
    }
    return true
  })

  router.afterEach((to) => {
    document.title = `${to.meta.title ?? 'Ресторан'} · Ресторан «Пряность»`
  })

  return router
}

export default createAppRouter()
