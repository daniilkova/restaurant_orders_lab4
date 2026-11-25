import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/orders', () => ({ fetchOrders: vi.fn() }))
vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), defaults: { baseURL: '' } },
  setUnauthorizedHandler: vi.fn(),
}))
const push = vi.fn()
let query = { redirect: '/' }
vi.mock('vue-router', async (orig) => ({
  ...(await orig()),
  useRouter: () => ({ push }),
  useRoute: () => ({ query }),
  RouterLink: { props: ['to'], template: '<a><slot /></a>' },
}))

import { fetchOrders } from '@/api/orders'
import client from '@/api/client'
import OrdersView from '@/views/OrdersView.vue'
import LoginView from '@/views/LoginView.vue'
import RegisterView from '@/views/RegisterView.vue'
import VerifyEmailView from '@/views/VerifyEmailView.vue'

const ORDER = {
  id: 7, status: 'готовится', created_at: '2026-11-24T10:00:00Z', total: 640,
  items: [{ dish_id: 1, dish_name: 'Борщ', quantity: 2, price: 320, subtotal: 640 }],
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  query = { redirect: '/' }
})

describe('OrdersView', () => {
  it('загрузка, затем список', async () => {
    fetchOrders.mockResolvedValue([ORDER])
    const w = mount(OrdersView)
    expect(w.text()).toContain('Загрузка')
    await flushPromises()
    expect(w.text()).toContain('Заказ №7')
    expect(w.find('.badge').text()).toBe('Готовится')
  })

  it('ошибка сети — «Повторить»', async () => {
    fetchOrders.mockRejectedValueOnce(new Error('x')).mockResolvedValueOnce([])
    const w = mount(OrdersView)
    await flushPromises()
    await w.find('.state--error button').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('Заказов пока нет')
  })
})

describe('LoginView', () => {
  async function fill(w, user = 'ivan', pass = 'Pizza2026') {
    await w.find('input[name=username]').setValue(user)
    await w.find('input[name=password]').setValue(pass)
    await w.find('form').trigger('submit')
    await flushPromises()
  }

  it('без 2FA — вход и переход по redirect', async () => {
    client.post.mockResolvedValue({ data: { access_token: 't' } })
    client.get.mockResolvedValue({ data: { username: 'ivan', role: 'client' } })
    await fill(mount(LoginView))
    expect(push).toHaveBeenCalledWith('/')
  })

  it('с 2FA — второй шаг: код из приложения', async () => {
    client.post
      .mockResolvedValueOnce({ data: { '2fa_required': true, temp_token: 'tmp' } })
      .mockResolvedValueOnce({ data: {} })
    client.get.mockResolvedValue({ data: { username: 'ivan', role: 'client' } })
    const w = mount(LoginView)
    await fill(w)
    expect(w.text()).toContain('Код подтверждения')
    expect(push).not.toHaveBeenCalled()
    await w.find('input[name=code]').setValue('12345')
    await w.find('form').trigger('submit')
    expect(w.text()).toContain('Введите 6 цифр')
    await w.find('input[name=code]').setValue('123456')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(client.post).toHaveBeenLastCalledWith('/auth/2fa/verify', { temp_token: 'tmp', code: '123456' })
    expect(push).toHaveBeenCalledWith('/')
  })

  it('неверный код 2FA — сообщение, поле очищено', async () => {
    client.post
      .mockResolvedValueOnce({ data: { '2fa_required': true, temp_token: 'tmp' } })
      .mockRejectedValueOnce({ response: { status: 401, data: { detail: 'Invalid 2FA code' } } })
    const w = mount(LoginView)
    await fill(w)
    await w.find('input[name=code]').setValue('000000')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.find('[role=alert]').text()).toBe('Неверный или устаревший код')
  })

  it('email не подтверждён — подсказка со ссылкой', async () => {
    client.post.mockRejectedValue({ response: { status: 403, data: { detail: 'email_not_verified' } } })
    const w = mount(LoginView)
    await fill(w)
    expect(w.find('[role=status]').text()).toContain('Email ещё не подтверждён')
  })
})

describe('RegisterView', () => {
  async function submit(w) {
    await w.find('input[name=username]').setValue('ivan')
    await w.find('input[name=email]').setValue('ivan@mail.ru')
    await w.find('input[name=password]').setValue('Pizza2026')
    await w.find('input[name=confirm]').setValue('Pizza2026')
    await w.find('form').trigger('submit')
    await flushPromises()
  }

  it('клиентская валидация: пароли не совпадают', async () => {
    const w = mount(RegisterView)
    await w.find('input[name=password]').setValue('Pizza2026')
    await w.find('input[name=confirm]').setValue('Pizza2027')
    await w.find('form').trigger('submit')
    expect(w.text()).toContain('Пароли не совпадают')
    expect(client.post).not.toHaveBeenCalled()
  })

  it('409 — ошибка под полем email', async () => {
    client.post.mockRejectedValue({ response: { status: 409, data: { detail: { field: 'email' } } } })
    const w = mount(RegisterView)
    await submit(w)
    expect(w.text()).toContain('Этот email уже зарегистрирован')
  })

  it('успех — экран «Проверьте почту»', async () => {
    client.post.mockResolvedValue({ data: { email: 'ivan@mail.ru', requires_age_verification: false } })
    const w = mount(RegisterView)
    await submit(w)
    expect(w.text()).toContain('Проверьте почту')
    expect(w.text()).toContain('ivan@mail.ru')
  })

  it('требуется возраст — токен регистрации в sessionStorage и переход на /verify-age', async () => {
    client.post.mockResolvedValue({ data: { requires_age_verification: true, registration_token: 'rt' } })
    await submit(mount(RegisterView))
    expect(sessionStorage.getItem('registration_token')).toBe('rt')
    expect(push).toHaveBeenCalledWith({ name: 'verify-age', query: { registration: 'true' } })
  })
})

describe('VerifyEmailView', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('ожидание не влияет на запрос, затем успех и обратный отсчёт до перехода', async () => {
    query = { token: 'abc' }
    let resolve
    client.get.mockImplementation(() => new Promise((r) => (resolve = r)))
    const w = mount(VerifyEmailView)
    await vi.advanceTimersByTimeAsync(2100)
    expect(w.text()).toContain('Ожидание: 2 с')
    expect(client.get).toHaveBeenCalledTimes(1)
    resolve({ data: { verified: true } })
    await flushPromises()
    expect(w.text()).toContain('Email подтверждён')
    await vi.advanceTimersByTimeAsync(5100)
    expect(push).toHaveBeenCalledWith({ name: 'login' })
  })

  it('уход со страницы до конца отсчёта — таймер очищен', async () => {
    query = { token: 'abc' }
    client.get.mockResolvedValue({ data: { verified: true } })
    const w = mount(VerifyEmailView)
    await flushPromises()
    w.unmount()
    await vi.advanceTimersByTimeAsync(6000)
    expect(push).not.toHaveBeenCalled()
  })

  it('устаревшая ссылка — форма повторной отправки', async () => {
    query = { token: 'old' }
    client.get.mockRejectedValue({ response: { status: 400, data: {} } })
    client.post.mockResolvedValue({ data: {} })
    const w = mount(VerifyEmailView)
    await flushPromises()
    expect(w.text()).toContain('недействительна или устарела')
    await w.find('input[type=email]').setValue('ivan@mail.ru')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(client.post).toHaveBeenCalledWith('/auth/resend-verification', { email: 'ivan@mail.ru' })
    expect(w.text()).toContain('мы отправили новое письмо')
  })
})
