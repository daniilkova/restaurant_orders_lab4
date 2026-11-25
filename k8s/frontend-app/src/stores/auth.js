// Состояние аутентификации. Сессия — в httpOnly cookies, поэтому признак входа — загруженный
// профиль (GET /auth/me), а не токен в localStorage.
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import client from '@/api/client'

const STAFF = ['moderator', 'admin']

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const ready = ref(false)
  let initPromise = null

  const isAuthenticated = computed(() => Boolean(user.value))
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isStaff = computed(() => STAFF.includes(user.value?.role))
  const displayName = computed(() => user.value?.display_name || user.value?.username || '')

  async function fetchMe() {
    const { data } = await client.get('/auth/me')
    user.value = data
    return data
  }

  // Один раз при старте приложения: есть ли действующая сессия (cookie)
  function init() {
    initPromise ??= fetchMe()
      .catch(() => {
        user.value = null
      })
      .finally(() => {
        ready.value = true
      })
    return initPromise
  }

  /** Возвращает { twoFactorRequired, tempToken } — второй шаг нужен, если включена 2FA. */
  async function login(username, password) {
    const body = new URLSearchParams({ username, password })
    const { data } = await client.post('/auth/token', body, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    if (data['2fa_required']) {
      return { twoFactorRequired: true, tempToken: data.temp_token }
    }
    await fetchMe()
    return { twoFactorRequired: false }
  }

  async function verifyTwoFactor(tempToken, code) {
    await client.post('/auth/2fa/verify', { temp_token: tempToken, code })
    await fetchMe()
  }

  async function register(payload) {
    const { data } = await client.post('/auth/register', payload)
    return data
  }

  async function logout() {
    try {
      await client.post('/auth/logout')
    } finally {
      clear()
    }
  }

  function clear() {
    user.value = null
  }

  return { user, ready, isAuthenticated, isAdmin, isStaff, displayName, init, fetchMe, login, verifyTwoFactor, register, logout, clear }
})
