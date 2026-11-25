import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import BaseButton from '../BaseButton.vue'

describe('BaseButton', () => {
  it('рендерит слот и по умолчанию type="button"', () => {
    const w = mount(BaseButton, { slots: { default: 'Сохранить' } })
    expect(w.text()).toBe('Сохранить')
    expect(w.attributes('type')).toBe('button')
  })

  it('эмитит click один раз', async () => {
    const w = mount(BaseButton, { slots: { default: 'OK' } })
    await w.trigger('click')
    expect(w.emitted('click')).toHaveLength(1)
  })

  it('disabled — клик не проходит', async () => {
    const w = mount(BaseButton, { props: { disabled: true } })
    expect(w.attributes('disabled')).toBeDefined()
    await w.trigger('click')
    expect(w.emitted('click')).toBeUndefined()
  })

  it('loading — спиннер, aria-busy и блокировка', () => {
    const w = mount(BaseButton, { props: { loading: true } })
    expect(w.find('.btn__spinner').exists()).toBe(true)
    expect(w.attributes('aria-busy')).toBe('true')
    expect(w.attributes('disabled')).toBeDefined()
  })

  it.each(['primary', 'secondary', 'danger', 'ghost'])('вариант %s задаёт класс', (variant) => {
    const w = mount(BaseButton, { props: { variant } })
    expect(w.classes()).toContain(`btn--${variant}`)
  })

  it('атрибуты родителя попадают на <button>', () => {
    const w = mount(BaseButton, { attrs: { 'aria-label': 'Закрыть', 'data-test': 'x' } })
    expect(w.attributes('aria-label')).toBe('Закрыть')
    expect(w.attributes('data-test')).toBe('x')
  })
})
