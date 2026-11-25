import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
  TOKEN_KEY: 'access_token',
  setUnauthorizedHandler: vi.fn(),
}))

import client from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { createAppRouter, safeRedirect } from '@/router'

describe('auth store', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('login отправляет form-urlencoded и сохраняет токен', async () => {
    client.post.mockResolvedValue({ data: { access_token: 'abc' } })
    client.get.mockResolvedValue({ data: { username: 'ivan', role: 'user' } })
    const auth = useAuthStore()
    await auth.login('ivan', 'Pizza2026')

    const [url, body, config] = client.post.mock.calls[0]
    expect(url).toBe('/auth/token')
    expect(body).toBeInstanceOf(URLSearchParams)
    expect(body.get('username')).toBe('ivan')
    expect(config.headers['Content-Type']).toBe('application/x-www-form-urlencoded')
    expect(localStorage.getItem('access_token')).toBe('abc')
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.user.username).toBe('ivan')
  })

  it('logout очищает токен и пользователя', () => {
    localStorage.setItem('access_token', 'abc')
    const auth = useAuthStore()
    auth.logout()
    expect(auth.isAuthenticated).toBe(false)
    expect(localStorage.getItem('access_token')).toBeNull()
  })
})

describe('router guard', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('без токена уводит на /login с redirect', async () => {
    const router = createAppRouter(createMemoryHistory())
    await router.push('/')
    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/')
  })

  it('с токеном пускает на главную, а с /login — уводит на главную', async () => {
    localStorage.setItem('access_token', 'abc')
    client.get.mockResolvedValue({ data: { username: 'ivan', role: 'user' } })
    const router = createAppRouter(createMemoryHistory())
    await router.push('/')
    expect(router.currentRoute.value.name).toBe('home')
    await router.push('/login')
    expect(router.currentRoute.value.name).toBe('home')
  })

  it('неизвестный адрес — страница 404', async () => {
    const router = createAppRouter(createMemoryHistory())
    await router.push('/nope')
    expect(router.currentRoute.value.name).toBe('not-found')
  })

  it('safeRedirect не допускает внешние адреса', () => {
    expect(safeRedirect('/orders')).toBe('/orders')
    expect(safeRedirect('//evil.example')).toBe('/')
    expect(safeRedirect('https://evil.example')).toBe('/')
    expect(safeRedirect(undefined)).toBe('/')
  })
})
