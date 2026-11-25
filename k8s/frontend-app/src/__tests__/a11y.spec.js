import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), defaults: { baseURL: '/api' } },
  setUnauthorizedHandler: vi.fn(),
}))

import client from '@/api/client'
import { mountView } from '@/test-utils'
import App from '@/App.vue'
import AccountView from '@/views/AccountView.vue'
import TurnstileWidget from '@/components/TurnstileWidget.vue'
import ToastNotification from '@/components/ui/ToastNotification.vue'
import { useAuthStore } from '@/stores/auth'
import { createPinia, setActivePinia } from 'pinia'

beforeEach(() => {
  vi.clearAllMocks()
  document.body.innerHTML = ''
})

describe('App: навигация с клавиатуры', () => {
  it('skip link ведёт к #main, а main может получить фокус', async () => {
    const { wrapper } = await mountView(App, { role: 'client' })
    const skip = wrapper.find('a.skip-link')
    expect(skip.attributes('href')).toBe('#main')
    expect(wrapper.find('main#main').attributes('tabindex')).toBe('-1')
  })

  it('кнопка меню на мобильных: aria-expanded и aria-controls', async () => {
    const { wrapper } = await mountView(App, { role: 'client' })
    const burger = wrapper.find('button.burger')
    expect(burger.attributes('aria-controls')).toBe('main-nav')
    expect(burger.attributes('aria-expanded')).toBe('false')
    await burger.trigger('click')
    expect(burger.attributes('aria-expanded')).toBe('true')
    expect(wrapper.find('#main-nav').classes()).toContain('nav--open')
  })

  it('при переходе фокус переносится на заголовок новой страницы', async () => {
    client.get.mockResolvedValue({ data: [] })
    const { wrapper, router } = await mountView(App, { role: 'client', path: '/' })
    await router.push('/orders')
    await flushPromises()
    await vi.waitFor(() => expect(document.activeElement?.tagName).toBe('H1'))
    expect(wrapper.find('[aria-live=polite]').exists()).toBe(true)
  })
})

describe('AccountView: вкладки по паттерну WAI-ARIA', () => {
  const stubs = { ProfileTab: { template: '<p>p</p>' }, SettingsTab: { template: '<p>s</p>' }, SecurityTab: { template: '<p>b</p>' } }

  it('стрелки и Home/End переключают вкладки; tabindex только у активной', async () => {
    const { wrapper } = await mountView(AccountView, { path: '/account', role: 'client', stubs })
    const tabs = () => wrapper.findAll('[role=tab]')
    expect(tabs().map((t) => t.attributes('tabindex'))).toEqual(['0', '-1', '-1'])
    await tabs()[0].trigger('keydown', { key: 'ArrowRight' })
    expect(tabs()[1].attributes('aria-selected')).toBe('true')
    await tabs()[1].trigger('keydown', { key: 'End' })
    expect(tabs()[2].attributes('aria-selected')).toBe('true')
    await tabs()[2].trigger('keydown', { key: 'ArrowRight' })
    expect(tabs()[0].attributes('aria-selected')).toBe('true') // по кругу
    await tabs()[0].trigger('keydown', { key: 'ArrowLeft' })
    expect(tabs()[2].attributes('aria-selected')).toBe('true')
    expect(wrapper.find('[role=tabpanel]:not([style*="display: none"])').attributes('aria-labelledby')).toBe('tab-security')
  })
})

describe('Уведомления и капча', () => {
  it('toast успеха — role=status и aria-live=polite, ошибки — assertive', () => {
    const ok = mount(ToastNotification, { props: { type: 'success', message: 'ok' } })
    expect(ok.attributes('aria-live')).toBe('polite')
    const err = mount(ToastNotification, { props: { type: 'error', message: 'x' } })
    expect(err.attributes('aria-live')).toBe('assertive')
  })

  it('без VITE_TURNSTILE_SITE_KEY виджет не рендерится', () => {
    const w = mount(TurnstileWidget)
    expect(w.find('.captcha').exists()).toBe(false)
    expect(w.vm.enabled).toBe(false)
  })

  it('токен капчи уходит в заголовке X-Turnstile-Token', async () => {
    setActivePinia(createPinia())
    client.post.mockResolvedValue({ data: {} })
    client.get.mockResolvedValue({ data: { username: 'ivan', role: 'client' } })
    await useAuthStore().login('ivan', 'Pizza2026', 'tok-123')
    expect(client.post.mock.calls[0][2].headers['X-Turnstile-Token']).toBe('tok-123')
  })
})
