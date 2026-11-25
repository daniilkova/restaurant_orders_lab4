// Глобальные уведомления. Массив объявлен на уровне модуля: все вызовы useToast()
// работают с одним списком, поэтому toast из любого экрана видит ToastContainer в App.vue.
import { readonly, ref } from 'vue'

const MAX_TOASTS = 5
const DURATION = { success: 3500, info: 3500, error: 6000 }
const toasts = ref([])
const timers = new Map()
let nextId = 1

function remove(id) {
  clearTimeout(timers.get(id))
  timers.delete(id)
  toasts.value = toasts.value.filter((t) => t.id !== id)
}

function show(type, message) {
  const id = nextId++
  toasts.value.push({ id, type, message })
  while (toasts.value.length > MAX_TOASTS) remove(toasts.value[0].id)
  timers.set(id, setTimeout(() => remove(id), DURATION[type] ?? 3500))
  return id
}

export function useToast() {
  return {
    toasts: readonly(toasts),
    success: (message) => show('success', message),
    error: (message) => show('error', message),
    info: (message) => show('info', message),
    remove,
  }
}

// для тестов
export function _resetToasts() {
  for (const id of Array.from(timers.keys())) remove(id) // копия: remove меняет Map
  toasts.value = []
}
