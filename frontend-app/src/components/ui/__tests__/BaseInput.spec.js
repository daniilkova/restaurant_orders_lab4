import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseInput from '../BaseInput.vue'

describe('BaseInput', () => {
  it('подпись связана с полем через for/id', () => {
    const w = mount(BaseInput, { props: { label: 'Название', id: 'name' } })
    expect(w.find('label').attributes('for')).toBe('name')
    expect(w.find('input').attributes('id')).toBe('name')
  })

  it('v-model: ввод эмитит update:modelValue', async () => {
    const w = mount(BaseInput, { props: { label: 'Х', modelValue: '' } })
    await w.find('input').setValue('Борщ')
    expect(w.emitted('update:modelValue')[0]).toEqual(['Борщ'])
  })

  it('number: строка превращается в число, пустая — в null', async () => {
    const w = mount(BaseInput, { props: { label: 'Цена', number: true, modelValue: null } })
    await w.find('input').setValue('450')
    await w.find('input').setValue('')
    expect(w.emitted('update:modelValue')).toEqual([[450], [null]])
  })

  it('ошибка: aria-invalid, aria-describedby и текст', () => {
    const w = mount(BaseInput, { props: { label: 'Х', id: 'p', error: 'Укажите цену' } })
    const input = w.find('input')
    expect(input.attributes('aria-invalid')).toBe('true')
    expect(input.attributes('aria-describedby')).toBe('p-error')
    expect(w.find('#p-error').text()).toBe('Укажите цену')
  })

  it('подсказка видна, пока нет ошибки', () => {
    const w = mount(BaseInput, { props: { label: 'Х', id: 'd', hint: 'Состав' } })
    expect(w.find('#d-hint').text()).toBe('Состав')
    expect(w.find('input').attributes('aria-describedby')).toBe('d-hint')
  })

  it('атрибуты (min, maxlength) идут на input, а не на обёртку', () => {
    const w = mount(BaseInput, { props: { label: 'Х' }, attrs: { maxlength: '100', placeholder: 'п' } })
    expect(w.find('input').attributes('maxlength')).toBe('100')
    expect(w.attributes('maxlength')).toBeUndefined()
  })

  it('multiline — textarea', () => {
    const w = mount(BaseInput, { props: { label: 'Описание', multiline: true } })
    expect(w.find('textarea').exists()).toBe(true)
  })
})
