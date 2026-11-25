// Монтирование экрана с настоящим роутером (в памяти) и Pinia с заданной ролью
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'
import { createAppRouter } from '@/router'
import { useAuthStore } from '@/stores/auth'

export async function mountView(component, { path = '/', role = 'admin', props = {} } = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  localStorage.setItem('access_token', 't')
  const auth = useAuthStore()
  auth.user = { id: 1, username: role, role }
  const router = createAppRouter(createMemoryHistory())
  await router.push(path)
  await router.isReady()
  const wrapper = mount(component, { props, global: { plugins: [pinia, router] }, attachTo: document.body })
  await flushPromises()
  return { wrapper, router, auth }
}
