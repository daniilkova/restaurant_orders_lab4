import { describe, expect, it, vi } from 'vitest'
import { reactive, readonly } from 'vue'
import { useForm } from '../useForm'

const required = (v) => (!v ? 'Обязательное поле' : '')

describe('useForm', () => {
  it('не отправляет форму с ошибками валидации', async () => {
    const onSubmit = vi.fn()
    const form = useForm({ name: '' }, { name: required }, onSubmit)
    expect(await form.submit()).toBe(false)
    expect(form.errors.name).toBe('Обязательное поле')
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('отправляет валидную форму с копией значений', async () => {
    const onSubmit = vi.fn().mockResolvedValue()
    const form = useForm({ name: 'Борщ' }, { name: required }, onSubmit)
    expect(await form.submit()).toBe(true)
    expect(onSubmit).toHaveBeenCalledWith({ name: 'Борщ' })
  })

  it('422 FastAPI раскладывается по полям (loc[1])', async () => {
    const error = {
      response: {
        status: 422,
        data: { detail: [{ type: 'less_than_equal', loc: ['body', 'price'], msg: 'x', ctx: { le: 100000 } }] },
      },
    }
    const form = useForm({ name: 'A', price: 1e6 }, {}, () => Promise.reject(error))
    await form.submit()
    expect(form.errors.price).toBe('Значение должно быть не больше 100000')
    expect(form.submitError.value).toBe('')
  })

  it('ошибка по полю, которого нет в форме, показывается общей', async () => {
    const error = { response: { status: 422, data: { detail: [{ type: 'extra_forbidden', loc: ['body', 'id'], msg: 'x' }] } } }
    const form = useForm({ name: 'A' }, {}, () => Promise.reject(error))
    await form.submit()
    expect(form.submitError.value).toBe('Лишнее поле')
  })

  it('прочие ошибки — общее сообщение', async () => {
    const form = useForm({ name: 'A' }, {}, () => Promise.reject({ response: { status: 403, data: {} } }))
    await form.submit()
    expect(form.submitError.value).toBe('Недостаточно прав для этого действия')
  })

  it('повторная отправка во время запроса игнорируется', async () => {
    let resolve
    const onSubmit = vi.fn(() => new Promise((r) => (resolve = r)))
    const form = useForm({ name: 'A' }, {}, onSubmit)
    const first = form.submit()
    expect(form.isSubmitting.value).toBe(true)
    expect(await form.submit()).toBe(false)
    resolve()
    await first
    expect(onSubmit).toHaveBeenCalledTimes(1)
  })

  it('работает с копией: исходный (даже readonly) объект не меняется', () => {
    const source = readonly(reactive({ name: 'A' }))
    const form = useForm(source, {}, vi.fn())
    form.values.name = 'B'
    expect(source.name).toBe('A')
    expect(form.isDirty.value).toBe(true)
    form.reset()
    expect(form.values.name).toBe('A')
  })

  it('валидатор получает все значения (правила между полями)', () => {
    const rule = vi.fn(() => '')
    const form = useForm({ a: 1, b: 2 }, { a: rule }, vi.fn())
    form.validateField('a')
    expect(rule).toHaveBeenCalledWith(1, expect.objectContaining({ a: 1, b: 2 }))
  })
})

describe('useForm: ошибка снимается при вводе', () => {
  it('после исправления значения ошибка исчезает без blur', async () => {
    const { nextTick } = await import('vue')
    const form = useForm({ name: '' }, { name: (v) => (!v ? 'Обязательное поле' : '') }, vi.fn())
    await form.submit()
    expect(form.errors.name).toBe('Обязательное поле')
    form.values.name = 'Борщ'
    await nextTick()
    expect(form.errors.name).toBe('')
  })
})
