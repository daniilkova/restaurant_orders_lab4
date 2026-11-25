import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn(), defaults: { baseURL: 'http://api' } },
  TOKEN_KEY: 'access_token',
  setUnauthorizedHandler: vi.fn(),
}))

import client from '@/api/client'
import { mountView } from '@/test-utils'
import { _resetToasts, useToast } from '@/composables/useToast'
import HomeView from '../HomeView.vue'
import DishDetailView from '../DishDetailView.vue'
import DishCreateView from '../DishCreateView.vue'
import DishEditView from '../DishEditView.vue'

const DISH = { id: 3, name: 'Пицца Маргарита', description: 'Сыр', price: 450, is_available: true, image_url: null }

beforeEach(() => {
  vi.clearAllMocks()
  _resetToasts()
})
afterEach(() => {
  document.body.innerHTML = ''
})

describe('HomeView (меню)', () => {
  it('карточки блюд и кнопка «+ Добавить» для администратора', async () => {
    client.get.mockResolvedValue({ data: [DISH, { ...DISH, id: 4, name: 'Борщ' }] })
    const { wrapper } = await mountView(HomeView)
    expect(wrapper.findAll('li.dish')).toHaveLength(2)
    expect(wrapper.text()).toContain('+ Добавить')
    expect(wrapper.find('a[href="/dishes/3"]').exists()).toBe(true)
  })

  it('клиент не видит «+ Добавить»', async () => {
    client.get.mockResolvedValue({ data: [DISH] })
    const { wrapper } = await mountView(HomeView, { role: 'user' })
    expect(wrapper.text()).not.toContain('+ Добавить')
  })

  it('поиск с задержкой', async () => {
    vi.useFakeTimers()
    client.get.mockResolvedValue({ data: [DISH, { ...DISH, id: 4, name: 'Борщ', description: null }] })
    const { wrapper } = await mountView(HomeView)
    await wrapper.find('input[type=search]').setValue('борщ')
    expect(wrapper.findAll('li.dish')).toHaveLength(2)
    await vi.advanceTimersByTimeAsync(350)
    expect(wrapper.findAll('li.dish')).toHaveLength(1)
    await wrapper.find('input[type=search]').setValue('суши')
    await vi.advanceTimersByTimeAsync(350)
    expect(wrapper.text()).toContain('Ничего не найдено')
    vi.useRealTimers()
  })

  it('ошибка сети — «Повторить»', async () => {
    client.get.mockRejectedValueOnce(new Error('Network Error')).mockResolvedValueOnce({ data: [DISH] })
    const { wrapper } = await mountView(HomeView)
    expect(wrapper.text()).toContain('Сервер недоступен')
    await wrapper.find('.state--error button').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('li.dish')).toHaveLength(1)
  })
})

describe('DishDetailView', () => {
  it('показывает поля и удаляет через модалку', async () => {
    client.get.mockResolvedValue({ data: DISH })
    client.delete.mockResolvedValue({})
    const { wrapper, router } = await mountView(DishDetailView, { path: '/dishes/3', props: { id: '3' } })
    expect(wrapper.text()).toContain('Пицца Маргарита')
    expect(wrapper.text()).toContain('В продаже')
    await wrapper.findAll('button').find((b) => b.text() === 'Удалить').trigger('click')
    await flushPromises()
    const confirm = [...document.body.querySelectorAll('[role=dialog] button')].find((b) => b.textContent.includes('Удалить'))
    confirm.click()
    await flushPromises()
    expect(client.delete).toHaveBeenCalledWith('/dishes/3')
    expect(useToast().toasts.value[0].message).toContain('удалено')
    expect(router.currentRoute.value.name).toBe('home')
  })

  it('отмена удаления — запись на месте', async () => {
    client.get.mockResolvedValue({ data: DISH })
    const { wrapper } = await mountView(DishDetailView, { path: '/dishes/3', props: { id: '3' } })
    await wrapper.findAll('button').find((b) => b.text() === 'Удалить').trigger('click')
    await flushPromises()
    ;[...document.body.querySelectorAll('[role=dialog] button')].find((b) => b.textContent === 'Отмена').click()
    await flushPromises()
    expect(client.delete).not.toHaveBeenCalled()
  })

  it('409 при удалении — уведомление с объяснением, окно открыто', async () => {
    client.get.mockResolvedValue({ data: DISH })
    client.delete.mockRejectedValue({
      response: { status: 409, data: { detail: 'Dish is used in orders; set is_available=false instead of deleting' } },
    })
    const { wrapper } = await mountView(DishDetailView, { path: '/dishes/3', props: { id: '3' } })
    await wrapper.findAll('button').find((b) => b.text() === 'Удалить').trigger('click')
    await flushPromises()
    ;[...document.body.querySelectorAll('[role=dialog] button')].find((b) => b.textContent.includes('Удалить')).click()
    await flushPromises()
    expect(useToast().toasts.value[0].message).toContain('Снимите его с продажи')
    expect(document.body.querySelector('[role=dialog]')).not.toBeNull()
  })

  it('404 — «Запись не найдена»', async () => {
    client.get.mockRejectedValue({ response: { status: 404, data: { detail: 'Dish not found' } } })
    const { wrapper } = await mountView(DishDetailView, { path: '/dishes/99', props: { id: '99' } })
    expect(wrapper.text()).toContain('Запись не найдена')
  })

  it('клиент не видит кнопок изменения', async () => {
    client.get.mockResolvedValue({ data: DISH })
    const { wrapper } = await mountView(DishDetailView, { path: '/dishes/3', props: { id: '3' }, role: 'user' })
    expect(wrapper.text()).not.toContain('Редактировать')
    expect(wrapper.text()).not.toContain('Удалить')
  })
})

describe('Create / Edit', () => {
  it('создание: POST и переход на детали', async () => {
    client.post.mockResolvedValue({ data: { ...DISH, id: 10, name: 'Борщ' } })
    const { wrapper, router } = await mountView(DishCreateView, { path: '/dishes/create' })
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('Борщ')
    await inputs[1].setValue('320')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(client.post).toHaveBeenCalledWith('/dishes/', { name: 'Борщ', description: null, price: 320, is_available: true })
    expect(router.currentRoute.value.fullPath).toBe('/dishes/10')
  })

  it('редактирование: форма после загрузки, PUT без id', async () => {
    client.get.mockResolvedValue({ data: DISH })
    client.put.mockResolvedValue({ data: { ...DISH, price: 500 } })
    const { wrapper, router } = await mountView(DishEditView, { path: '/dishes/3/edit', props: { id: '3' } })
    expect(wrapper.findAll('input')[0].element.value).toBe('Пицца Маргарита')
    await wrapper.findAll('input')[1].setValue('500')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    const [url, body] = client.put.mock.calls[0]
    expect(url).toBe('/dishes/3')
    expect(body).not.toHaveProperty('id')
    expect(body.price).toBe(500)
    expect(router.currentRoute.value.fullPath).toBe('/dishes/3')
  })

  it('редактирование удалённой записи — «Запись не найдена»', async () => {
    client.get.mockRejectedValue({ response: { status: 404, data: {} } })
    const { wrapper } = await mountView(DishEditView, { path: '/dishes/3/edit', props: { id: '3' } })
    expect(wrapper.text()).toContain('Запись не найдена')
    expect(wrapper.find('form').exists()).toBe(false)
  })
})
