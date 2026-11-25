<script setup>
// Модальное окно: Teleport в <body>, закрытие по Escape и клику по фону, ловушка фокуса
// (Tab не уходит за пределы окна) и возврат фокуса на элемент, открывший окно.
import { nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, required: true },
  persistent: { type: Boolean, default: false }, // идёт запрос — окно не закрывается
})
const emit = defineEmits(['close'])

const dialog = ref(null)
const titleId = `modal-title-${useId()}`
let previouslyFocused = null

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])'

function close() {
  if (!props.persistent) emit('close')
}

function onKeydown(event) {
  if (event.key === 'Escape') {
    event.stopPropagation()
    close()
    return
  }
  if (event.key === 'Tab' && dialog.value) {
    const items = [...dialog.value.querySelectorAll(FOCUSABLE)]
    if (items.length === 0) return
    const first = items[0]
    const last = items[items.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }
}

watch(
  () => props.open,
  async (isOpen) => {
    if (isOpen) {
      previouslyFocused = document.activeElement
      document.addEventListener('keydown', onKeydown)
      await nextTick()
      const preferred = dialog.value?.querySelector('[data-autofocus]') || dialog.value?.querySelector(FOCUSABLE)
      ;(preferred || dialog.value)?.focus()
    } else {
      document.removeEventListener('keydown', onKeydown)
      previouslyFocused?.focus?.()
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="modal" @mousedown.self="close">
        <div
          ref="dialog"
          class="modal__dialog"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="titleId"
          tabindex="-1"
        >
          <h2 :id="titleId" class="modal__title">{{ title }}</h2>
          <div class="modal__body"><slot /></div>
          <div v-if="$slots.actions" class="modal__actions"><slot name="actions" /></div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 16px;
  background: rgba(43, 33, 24, 0.45);
}
.modal__dialog {
  width: min(460px, 100%);
  padding: 24px;
  border-radius: var(--radius-lg, 16px);
  background: var(--color-surface, #fff);
  box-shadow: var(--shadow-lg, 0 10px 30px rgba(0, 0, 0, 0.2));
}
.modal__dialog:focus {
  outline: none;
}
.modal__title {
  margin: 0 0 8px;
  font-size: 20px;
}
.modal__body {
  color: var(--color-muted, #7a6a5b);
}
.modal__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.18s;
}
.modal-enter-active .modal__dialog,
.modal-leave-active .modal__dialog {
  transition: transform 0.18s;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .modal__dialog,
.modal-leave-to .modal__dialog {
  transform: translateY(8px) scale(0.98);
}
</style>
