import { describe, expect, it } from 'vitest'
import { errorMessage, parseValidationError } from '../errors'
import { toDishPayload } from '../dishes'

describe('errorMessage', () => {
  it('нет ответа — сервер недоступен', () => {
    expect(errorMessage(new Error('Network Error'))).toContain('Сервер недоступен')
  })
  it('409 при удалении блюда из заказов — понятный текст', () => {
    const err = { response: { status: 409, data: { detail: 'Dish is used in orders; set is_available=false instead of deleting' } } }
    expect(errorMessage(err)).toContain('Снимите его с продажи')
  })
  it.each([
    [403, 'Недостаточно прав'],
    [404, 'не найдена'],
    [500, 'Ошибка сервера'],
  ])('статус %i', (status, text) => {
    expect(errorMessage({ response: { status, data: {} } })).toContain(text)
  })
})

describe('parseValidationError', () => {
  it('ошибки из query не попадают в поля формы', () => {
    const err = { response: { status: 422, data: { detail: [{ type: 'missing', loc: ['query', 'q'], msg: 'x' }] } } }
    expect(parseValidationError(err, ['name'])).toEqual({ fieldErrors: {}, general: 'Обязательное поле' })
  })
  it('не 422 — пусто', () => {
    expect(parseValidationError({ response: { status: 500 } }, ['name'])).toEqual({ fieldErrors: {}, general: '' })
  })
})

describe('toDishPayload', () => {
  it('отбрасывает id и image_url, пустое описание -> null', () => {
    const payload = toDishPayload({ id: 3, image_url: '/x', name: ' Борщ ', description: '  ', price: 320, is_available: true })
    expect(payload).toEqual({ name: 'Борщ', description: null, price: 320, is_available: true })
  })
})
