import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(), defaults: { baseURL: '' } },
  setUnauthorizedHandler: vi.fn(),
}))

import client from '@/api/client'
import { mountView } from '@/test-utils'
import AccountView from '@/views/AccountView.vue'
import TwoFactorCard from '../TwoFactorCard.vue'
import SessionsCard from '../SessionsCard.vue'
import AgeVerificationCard from '../AgeVerificationCard.vue'

beforeEach(() => {
  vi.clearAllMocks()
  document.body.innerHTML = ''
})

describe('AccountView', () => {
  // Дочерние вкладки заменены заглушками: проверяем только шапку и переключение вкладок,
  // без сетевых запросов каждой карточки (их проверяют отдельные тесты)
  const stubs = { ProfileTab: { template: '<p>profile</p>' }, SettingsTab: { template: '<p>settings</p>' }, SecurityTab: { template: '<p>security</p>' } }

  it('шапка с ником и три вкладки с ARIA-ролями', async () => {
    const { wrapper } = await mountView(AccountView, { path: '/account', role: 'client', stubs })
    expect(wrapper.find('h1').text()).toBe('client')
    const tabs = wrapper.findAll('[role=tab]')
    expect(tabs.map((t) => t.text())).toEqual(['Профиль', 'Настройки', 'Безопасность'])
    expect(tabs[0].attributes('aria-selected')).toBe('true')
    await tabs[2].trigger('click')
    expect(wrapper.text()).toContain('security')
    expect(tabs[2].attributes('aria-selected')).toBe('true')
  })
})

describe('TwoFactorCard', () => {
  it('включение: QR и секрет, подтверждение кодом', async () => {
    client.post
      .mockResolvedValueOnce({ data: { secret: 'ABC', qr_svg: 'data:image/svg+xml;base64,x' } })
      .mockResolvedValueOnce({ data: { id: 1, username: 'client', role: 'client', totp_enabled: true } })
    const { wrapper, auth } = await mountView(TwoFactorCard, { role: 'client' })
    await wrapper.find('button').trigger('click')
    await flushPromises()
    expect(wrapper.find('img').attributes('src')).toContain('data:image/svg+xml')
    expect(wrapper.text()).toContain('ABC')
    await wrapper.find('input').setValue('123456')
    await wrapper.findAll('button').find((b) => b.text() === 'Подтвердить').trigger('click')
    await flushPromises()
    expect(client.post).toHaveBeenLastCalledWith('/auth/2fa/confirm', { code: '123456' })
    expect(auth.user.totp_enabled).toBe(true)
    expect(wrapper.text()).toContain('Включена')
  })

  it('неверный код — понятная ошибка', async () => {
    client.post
      .mockResolvedValueOnce({ data: { secret: 'ABC', qr_svg: 'x' } })
      .mockRejectedValueOnce({ response: { status: 400, data: {} } })
    const { wrapper } = await mountView(TwoFactorCard, { role: 'client' })
    await wrapper.find('button').trigger('click')
    await flushPromises()
    await wrapper.find('input').setValue('000000')
    await wrapper.findAll('button').find((b) => b.text() === 'Подтвердить').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Неверный код')
  })
})

describe('SessionsCard', () => {
  const SESSIONS = [
    { id: 'a', current: true, user_agent: 'Mozilla/5.0 (Windows NT 10.0) Chrome/130', ip: '1.1.1.1', created_at: '2026-11-24T08:00:00Z', last_used_at: '2026-11-24T09:00:00Z' },
    { id: 'b', current: false, user_agent: 'Mozilla/5.0 (Android 14) Firefox/131', ip: '2.2.2.2', created_at: '2026-11-20T08:00:00Z', last_used_at: '2026-11-21T09:00:00Z' },
  ]

  it('список устройств и завершение чужой сессии', async () => {
    client.get.mockResolvedValue({ data: SESSIONS })
    client.delete.mockResolvedValue({})
    const { wrapper } = await mountView(SessionsCard, { role: 'client' })
    expect(wrapper.text()).toContain('Chrome, Windows')
    expect(wrapper.text()).toContain('это устройство')
    await wrapper.findAll('.item button')[1].trigger('click')
    await flushPromises()
    expect(client.delete).toHaveBeenCalledWith('/auth/sessions/b')
    expect(wrapper.findAll('.item')).toHaveLength(1)
  })

  it('завершение текущей сессии — выход и переход на /login', async () => {
    client.get.mockResolvedValue({ data: SESSIONS })
    client.delete.mockResolvedValue({})
    const { wrapper, router, auth } = await mountView(SessionsCard, { role: 'client' })
    await wrapper.findAll('.item button')[0].trigger('click')
    await flushPromises()
    expect(auth.user).toBeNull()
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('login'))
  })
})

describe('AgeVerificationCard', () => {
  it('без профиля карточка скрыта, а не показывает ошибку', async () => {
    const { wrapper } = await mountView(AgeVerificationCard, { role: null })
    expect(wrapper.html()).not.toContain('Возрастная верификация')
  })

  it('не пройдена — кнопка запускает сессию Self', async () => {
    const assign = vi.fn()
    vi.stubGlobal('location', { ...window.location, assign })
    client.post.mockResolvedValue({ data: { verificationUrl: 'https://self.example/s/1' } })
    const { wrapper } = await mountView(AgeVerificationCard, { role: 'client' })
    expect(wrapper.text()).toContain('Не пройдена')
    await wrapper.find('button').trigger('click')
    await flushPromises()
    expect(client.post).toHaveBeenCalledWith('/auth/age-session', null, { headers: {} })
    expect(assign).toHaveBeenCalledWith('https://self.example/s/1')
    vi.unstubAllGlobals()
  })
})
