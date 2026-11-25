import { afterEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import BaseModal from '../BaseModal.vue'

function mountModal(props = {}) {
  return mount(BaseModal, {
    props: { open: true, title: 'Удалить?', ...props },
    slots: { default: 'Текст', actions: '<button data-autofocus>Отмена</button><button>Удалить</button>' },
    attachTo: document.body,
  })
}

describe('BaseModal', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('телепортируется в body и имеет role=dialog', async () => {
    const w = mountModal()
    await nextTick()
    const dialog = document.body.querySelector('[role=dialog]')
    expect(dialog).not.toBeNull()
    expect(dialog.getAttribute('aria-modal')).toBe('true')
    expect(document.getElementById(dialog.getAttribute('aria-labelledby')).textContent).toBe('Удалить?')
    w.unmount()
  })

  it('Escape закрывает окно', async () => {
    const w = mountModal()
    await nextTick()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(w.emitted('close')).toHaveLength(1)
    w.unmount()
  })

  it('persistent — Escape не закрывает (идёт запрос)', async () => {
    const w = mountModal({ persistent: true })
    await nextTick()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(w.emitted('close')).toBeUndefined()
    w.unmount()
  })

  it('фокус переходит на элемент с data-autofocus', async () => {
    const w = mountModal()
    await nextTick()
    await nextTick()
    expect(document.activeElement.textContent).toBe('Отмена')
    w.unmount()
  })

  it('закрытое окно не рендерится и слушатель снят', async () => {
    const w = mountModal({ open: false })
    await nextTick()
    expect(document.body.querySelector('[role=dialog]')).toBeNull()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(w.emitted('close')).toBeUndefined()
    w.unmount()
  })
})
