// HTTP-клиент: единая точка общения с FastAPI.
import axios from 'axios'

export const TOKEN_KEY = 'access_token'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 10000,
})

// Request interceptor: к каждому запросу добавляем JWT, если он есть
client.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Обработчик 401 назначает приложение (main.js): store выходит и роутер уводит на /login.
// Так клиент не импортирует store и router, и нет циклических зависимостей.
let onUnauthorized = null
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler
}

// Response interceptor: 401 = токен истёк или отозван — разлогиниваем
client.interceptors.response.use(
  (response) => response,
  (error) => {
    const isLoginRequest = error.config?.url?.includes('/auth/token')
    if (error.response?.status === 401 && !isLoginRequest && onUnauthorized) {
      onUnauthorized()
    }
    return Promise.reject(error)
  },
)

export default client
