import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import DishForm from '../DishForm.vue'

async function fill(w, { name = 'Борщ', price = '320' } = {}) {
  const inputs = w.findAll('input')
  await inputs[0].setValue(name)
  await inputs[1].setValue(price)
}

describe('DishForm', () => {
  it('валидная форма вызывает onSubmit с данными', async () => {
    const onSubmit = vi.fn().mockResolvedValue()
    const w = mount(DishForm, { props: { onSubmit } })
    await fill(w)
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(onSubmit).toHaveBeenCalledWith({ name: 'Борщ', description: '', price: 320, is_available: true, min_age: 0 })
  })

  it('пустая форма — ошибки под полями, запроса нет', async () => {
    const onSubmit = vi.fn()
    const w = mount(DishForm, { props: { onSubmit } })
    await w.find('form').trigger('submit')
    expect(w.text()).toContain('Введите название')
    expect(w.text()).toContain('Укажите цену')
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('422 от сервера показывается под полем цены', async () => {
    const onSubmit = vi.fn().mockRejectedValue({
      response: { status: 422, data: { detail: [{ type: 'less_than_equal', loc: ['body', 'price'], msg: 'x', ctx: { le: 100000 } }] } },
    })
    const w = mount(DishForm, { props: { onSubmit } })
    await fill(w, { price: '500000' })
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.text()).toContain('Значение должно быть не больше 100000')
  })

  it('режим редактирования: поля заполнены, родительский объект не меняется', async () => {
    const dish = Object.freeze({ id: 3, name: 'Пицца', description: 'Сыр', price: 450, is_available: false })
    const w = mount(DishForm, { props: { initialValues: dish, onSubmit: vi.fn() } })
    expect(w.findAll('input')[0].element.value).toBe('Пицца')
    expect(w.find('input[type=checkbox]').element.checked).toBe(false)
    await w.findAll('input')[0].setValue('Пицца 2')
    expect(dish.name).toBe('Пицца')
  })

  it('кнопка отправки показывает загрузку', async () => {
    let resolve
    const w = mount(DishForm, { props: { onSubmit: () => new Promise((r) => (resolve = r)) } })
    await fill(w)
    await w.find('form').trigger('submit')
    expect(w.find('button[type=submit]').attributes('aria-busy')).toBe('true')
    resolve()
    await flushPromises()
  })
})
