import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
  setUnauthorizedHandler: vi.fn(),
}))

import client from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { createAppRouter, safeRedirect } from '@/router'

const ME = { id: 1, username: 'ivan', role: 'client' }

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  localStorage.clear()
})

describe('auth store (сессия в httpOnly cookie)', () => {
  it('login: form-urlencoded, профиль из /auth/me, токен НЕ попадает в localStorage', async () => {
    client.post.mockResolvedValue({ data: { access_token: 'abc' } })
    client.get.mockResolvedValue({ data: ME })
    const auth = useAuthStore()
    const result = await auth.login('ivan', 'Pizza2026')
    const [url, body, config] = client.post.mock.calls[0]
    expect(url).toBe('/auth/token')
    expect(body.get('username')).toBe('ivan')
    expect(config.headers['Content-Type']).toBe('application/x-www-form-urlencoded')
    expect(result.twoFactorRequired).toBe(false)
    expect(auth.isAuthenticated).toBe(true)
    expect(JSON.stringify(localStorage)).not.toContain('abc')
  })

  it('login с 2FA: возвращает temp_token, вход ещё не выполнен', async () => {
    client.post.mockResolvedValue({ data: { '2fa_required': true, temp_token: 'tmp' } })
    const auth = useAuthStore()
    expect(await auth.login('ivan', 'x')).toEqual({ twoFactorRequired: true, tempToken: 'tmp' })
    expect(auth.isAuthenticated).toBe(false)
    expect(client.get).not.toHaveBeenCalled()
  })

  it('verifyTwoFactor отправляет код и загружает профиль', async () => {
    client.post.mockResolvedValue({ data: {} })
    client.get.mockResolvedValue({ data: ME })
    const auth = useAuthStore()
    await auth.verifyTwoFactor('tmp', '123456')
    expect(client.post).toHaveBeenCalledWith('/auth/2fa/verify', { temp_token: 'tmp', code: '123456' })
    expect(auth.user.username).toBe('ivan')
  })

  it('logout вызывает /auth/logout и очищает профиль даже при ошибке сети', async () => {
    client.post.mockRejectedValue(new Error('Network'))
    const auth = useAuthStore()
    auth.user = ME
    await expect(auth.logout()).rejects.toThrow('Network')
    expect(auth.user).toBeNull()
  })

  it('роли: модератор — персонал, но не администратор', () => {
    const auth = useAuthStore()
    auth.user = { ...ME, role: 'moderator' }
    expect(auth.isStaff).toBe(true)
    expect(auth.isAdmin).toBe(false)
  })

  it('init запрашивает /auth/me один раз', async () => {
    client.get.mockRejectedValue({ response: { status: 401 } })
    const auth = useAuthStore()
    await Promise.all([auth.init(), auth.init()])
    expect(client.get).toHaveBeenCalledTimes(1)
    expect(auth.ready).toBe(true)
  })
})

describe('router guard', () => {
  it('гость: / — лендинг, /orders — на /login с redirect', async () => {
    client.get.mockRejectedValue({ response: { status: 401 } })
    const router = createAppRouter(createMemoryHistory())
    await router.push('/')
    expect(router.currentRoute.value.name).toBe('home')
    await router.push('/orders')
    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/orders')
  })

  it('вошедший: /login и /register уводят на главную', async () => {
    client.get.mockResolvedValue({ data: ME })
    const router = createAppRouter(createMemoryHistory())
    await router.push('/register')
    expect(router.currentRoute.value.name).toBe('home')
  })

  it('клиента не пускает на создание блюда, модератора — пускает', async () => {
    client.get.mockResolvedValue({ data: ME })
    let router = createAppRouter(createMemoryHistory())
    await router.push('/dishes/create')
    expect(router.currentRoute.value.name).toBe('home')

    setActivePinia(createPinia())
    client.get.mockResolvedValue({ data: { ...ME, role: 'moderator' } })
    router = createAppRouter(createMemoryHistory())
    await router.push('/dishes/create')
    expect(router.currentRoute.value.name).toBe('dish-create')
  })

  it('/dishes/abc — 404; verify-email и verify-age доступны без входа', async () => {
    client.get.mockRejectedValue({ response: { status: 401 } })
    const router = createAppRouter(createMemoryHistory())
    await router.push('/dishes/abc')
    expect(router.currentRoute.value.name).toBe('not-found')
    await router.push('/verify-email?token=x')
    expect(router.currentRoute.value.name).toBe('verify-email')
    await router.push('/verify-age')
    expect(router.currentRoute.value.name).toBe('verify-age')
  })

  it('safeRedirect не допускает внешние адреса', () => {
    expect(safeRedirect('/orders')).toBe('/orders')
    expect(safeRedirect('//evil.example')).toBe('/')
    expect(safeRedirect('https://evil.example')).toBe('/')
  })
})
