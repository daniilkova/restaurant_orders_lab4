// Монтирование экрана с настоящим роутером (в памяти) и Pinia с заданной ролью
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'
import { createAppRouter } from '@/router'
import { useAuthStore } from '@/stores/auth'

export async function mountView(component, { path = '/', role = 'admin', props = {}, stubs = {} } = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.user = role ? { id: 1, username: role, role, is_email_verified: true, totp_enabled: false } : null
  auth.init = () => Promise.resolve() // сессия уже «восстановлена»
  const router = createAppRouter(createMemoryHistory())
  await router.push(path)
  await router.isReady()
  const wrapper = mount(component, { props, global: { plugins: [pinia, router], stubs }, attachTo: document.body })
  await flushPromises()
  return { wrapper, router, auth }
}
