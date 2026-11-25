import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/orders', () => ({ fetchOrders: vi.fn() }))
vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
  TOKEN_KEY: 'access_token',
  setUnauthorizedHandler: vi.fn(),
}))
const push = vi.fn()
vi.mock('vue-router', async (orig) => ({
  ...(await orig()),
  useRouter: () => ({ push }),
  useRoute: () => ({ query: { redirect: '/' } }),
}))

import { fetchOrders } from '@/api/orders'
import client from '@/api/client'
import HomeView from '@/views/HomeView.vue'
import LoginView from '@/views/LoginView.vue'

const ORDER = {
  id: 7,
  status: 'готовится',
  created_at: '2026-11-24T10:00:00Z',
  items: [{ dish_id: 1, dish_name: 'Борщ', quantity: 2, price: 320, subtotal: 640 }],
  total: 640,
}

describe('HomeView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('показывает загрузку, затем список заказов из API', async () => {
    fetchOrders.mockResolvedValue([ORDER])
    const wrapper = mount(HomeView)
    expect(wrapper.text()).toContain('Загрузка')
    await flushPromises()
    expect(wrapper.text()).toContain('Заказ №7')
    expect(wrapper.text()).toContain('Борщ × 2')
    expect(wrapper.find('.badge').text()).toBe('Готовится')
  })

  it('ошибка сети — сообщение и кнопка «Повторить»', async () => {
    fetchOrders.mockRejectedValueOnce(new Error('Network Error')).mockResolvedValueOnce([])
    const wrapper = mount(HomeView)
    await flushPromises()
    expect(wrapper.text()).toContain('Сервер недоступен')
    await wrapper.find('.state--error button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Заказов пока нет')
  })
})

describe('LoginView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('пустая форма не отправляется', async () => {
    const wrapper = mount(LoginView)
    await wrapper.find('form').trigger('submit')
    expect(wrapper.text()).toContain('Введите логин и пароль')
    expect(client.post).not.toHaveBeenCalled()
  })

  it('неверный пароль — понятная ошибка, пароль очищается', async () => {
    client.post.mockRejectedValue({ response: { status: 401, data: { detail: 'Incorrect username or password' } } })
    const wrapper = mount(LoginView)
    await wrapper.find('input[name=username]').setValue('ivan')
    await wrapper.find('input[name=password]').setValue('wrong')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.find('[role=alert]').text()).toBe('Неверный логин или пароль')
    expect(wrapper.find('input[name=password]').element.value).toBe('')
  })

  it('успешный вход — переход по redirect', async () => {
    client.post.mockResolvedValue({ data: { access_token: 't' } })
    client.get.mockResolvedValue({ data: { username: 'ivan', role: 'user' } })
    const wrapper = mount(LoginView)
    await wrapper.find('input[name=username]').setValue('ivan')
    await wrapper.find('input[name=password]').setValue('Pizza2026')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(push).toHaveBeenCalledWith('/')
  })
})
