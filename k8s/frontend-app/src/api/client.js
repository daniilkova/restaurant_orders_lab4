// HTTP-клиент. С ЛР8 токены лежат в httpOnly cookies: JavaScript их не видит (XSS не украдёт),
// браузер сам отправляет их с withCredentials. localStorage для токенов не используется.
import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 10000,
  withCredentials: true,
  // Защита от CSRF поверх SameSite=Strict: чужой сайт не может добавить этот заголовок без CORS
  headers: { 'X-Requested-With': 'XMLHttpRequest' },
})

let onUnauthorized = null
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler
}

// Эндпоинты, на которых 401 — это ответ по существу, а не истёкшая сессия
const NO_REFRESH = ['/auth/token', '/auth/refresh', '/auth/2fa/verify', '/auth/logout', '/auth/register']
let refreshing = null // один запрос обновления на все параллельные 401

export function refreshSession() {
  refreshing ??= client.post('/auth/refresh', null, { _skipRefresh: true }).finally(() => {
    refreshing = null
  })
  return refreshing
}

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config || {}
    const status = error.response?.status
    const skip = config._skipRefresh || config._retried || NO_REFRESH.some((url) => config.url?.includes(url))
    if (status === 401 && !skip) {
      try {
        // access-токен живёт 15 минут: продлеваем сессию по refresh-cookie и повторяем запрос
        await refreshSession()
        return client({ ...config, _retried: true })
      } catch {
        onUnauthorized?.()
      }
    }
    return Promise.reject(error)
  },
)

export default client
