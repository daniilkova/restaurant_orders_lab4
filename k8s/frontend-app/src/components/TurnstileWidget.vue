<script setup>
// Cloudflare Turnstile. Скрипт грузится один раз; без VITE_TURNSTILE_SITE_KEY виджет не показывается.
// Токен одноразовый: после каждой попытки входа/регистрации родитель вызывает reset().
import { onBeforeUnmount, onMounted, ref } from 'vue'

const emit = defineEmits(['update:token'])
const siteKey = import.meta.env.VITE_TURNSTILE_SITE_KEY
const container = ref(null)
const failed = ref(false)
let widgetId = null

let scriptPromise = null
function loadScript() {
  if (window.turnstile) return Promise.resolve(window.turnstile)
  scriptPromise ??= new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
    script.async = true
    script.onload = () => resolve(window.turnstile)
    script.onerror = reject
    document.head.appendChild(script)
  })
  return scriptPromise
}

onMounted(async () => {
  if (!siteKey) return
  try {
    const turnstile = await loadScript()
    widgetId = turnstile.render(container.value, {
      sitekey: siteKey,
      language: 'ru',
      callback: (token) => emit('update:token', token),
      'expired-callback': () => emit('update:token', ''),
      'error-callback': () => emit('update:token', ''),
    })
  } catch {
    failed.value = true
  }
})

onBeforeUnmount(() => {
  if (widgetId !== null) window.turnstile?.remove(widgetId)
})

defineExpose({
  reset() {
    emit('update:token', '')
    if (widgetId !== null) window.turnstile?.reset(widgetId)
  },
  enabled: Boolean(siteKey),
})
</script>

<template>
  <div v-if="siteKey" class="captcha">
    <div ref="container" />
    <p v-if="failed" class="captcha__error" role="alert">Не удалось загрузить проверку Cloudflare. Обновите страницу.</p>
  </div>
</template>

<style scoped>
.captcha { min-height: 65px; }
.captcha__error { margin: 4px 0 0; color: var(--color-danger); font-size: 14px; }
</style>
