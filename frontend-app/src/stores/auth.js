// Состояние аутентификации. Токен — в localStorage (переживает перезагрузку страницы)
// и в ref (реактивность: интерфейс сразу видит вход и выход).
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import client, { TOKEN_KEY } from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(TOKEN_KEY))
  const user = ref(null)

  const isAuthenticated = computed(() => Boolean(token.value))
  const isAdmin = computed(() => user.value?.role === 'admin')

  async function login(username, password) {
    // OAuth2 password flow: FastAPI ждёт application/x-www-form-urlencoded, а не JSON
    const body = new URLSearchParams({ username, password })
    const { data } = await client.post('/auth/token', body, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    token.value = data.access_token
    localStorage.setItem(TOKEN_KEY, data.access_token)
    await fetchMe()
  }

  async function fetchMe() {
    if (!token.value) return null
    const { data } = await client.get('/auth/me')
    user.value = data
    return data
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
  }

  return { token, user, isAuthenticated, isAdmin, login, fetchMe, logout }
})
