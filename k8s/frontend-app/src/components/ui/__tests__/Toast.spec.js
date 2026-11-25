import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { _resetToasts, useToast } from '@/composables/useToast'
import ToastNotification from '../ToastNotification.vue'
import ToastContainer from '../ToastContainer.vue'

describe('useToast', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    _resetToasts()
  })
  afterEach(() => vi.useRealTimers())

  it('одно состояние на всё приложение', () => {
    useToast().success('A')
    expect(useToast().toasts.value).toHaveLength(1)
  })

  it('уведомление исчезает само; ошибка держится дольше', () => {
    const t = useToast()
    t.success('ok')
    t.error('fail')
    vi.advanceTimersByTime(4000)
    expect(t.toasts.value.map((x) => x.message)).toEqual(['fail'])
    vi.advanceTimersByTime(2500)
    expect(t.toasts.value).toHaveLength(0)
  })

  it('не больше пяти уведомлений', () => {
    const t = useToast()
    for (let i = 0; i < 7; i++) t.info(`m${i}`)
    expect(t.toasts.value.map((x) => x.message)).toEqual(['m2', 'm3', 'm4', 'm5', 'm6'])
  })
})

describe('ToastNotification и ToastContainer', () => {
  beforeEach(() => _resetToasts())

  it('ошибка — role=alert, успех — role=status', () => {
    expect(mount(ToastNotification, { props: { type: 'error', message: 'x' } }).attributes('role')).toBe('alert')
    expect(mount(ToastNotification, { props: { type: 'success', message: 'x' } }).attributes('role')).toBe('status')
  })

  it('контейнер показывает уведомления и закрывает по кнопке', async () => {
    const w = mount(ToastContainer, { attachTo: document.body })
    useToast().success('Блюдо добавлено')
    await nextTick()
    expect(document.body.textContent).toContain('Блюдо добавлено')
    document.body.querySelector('.toast__close').click()
    await nextTick()
    expect(useToast().toasts.value).toHaveLength(0)
    w.unmount()
  })
})
