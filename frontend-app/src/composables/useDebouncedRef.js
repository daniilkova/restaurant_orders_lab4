import { onScopeDispose, ref, watch } from 'vue'

// Значение source с задержкой: обновляется, когда пользователь перестал печатать на delay мс
export function useDebounced(source, delay = 300) {
  const debounced = ref(source.value)
  let timer
  watch(source, (value) => {
    clearTimeout(timer)
    timer = setTimeout(() => {
      debounced.value = value
    }, delay)
  })
  onScopeDispose(() => clearTimeout(timer))
  return debounced
}
