// Универсальный CRUD для REST-ресурса: состояние загрузки, ошибки и данные в одном месте.
import { ref } from 'vue'
import client from '@/api/client'
import { errorMessage } from '@/api/errors'

function joinUrl(base, id) {
  const root = base.replace(/\/+$/, '')
  return id === undefined ? `${root}/` : `${root}/${id}`
}

export function useResource(endpoint) {
  const items = ref([])
  const item = ref(null)
  const isLoading = ref(false)
  const error = ref('')
  const notFound = ref(false)
  let listRequestId = 0

  async function run(action) {
    isLoading.value = true
    error.value = ''
    notFound.value = false
    try {
      return await action()
    } catch (err) {
      notFound.value = err?.response?.status === 404
      error.value = errorMessage(err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function fetchList(params = {}) {
    const requestId = ++listRequestId
    return run(async () => {
      const { data } = await client.get(joinUrl(endpoint), { params })
      // ответ на устаревший запрос (например, при быстром поиске) не перезаписывает новый
      if (requestId === listRequestId) items.value = data
      return data
    }).catch(() => null)
  }

  async function fetchOne(id) {
    return run(async () => {
      const { data } = await client.get(joinUrl(endpoint, id))
      item.value = data
      return data
    }).catch(() => null)
  }

  async function create(payload) {
    const { data } = await client.post(joinUrl(endpoint), payload)
    items.value = [...items.value, data]
    return data
  }

  async function update(id, payload) {
    const { data } = await client.put(joinUrl(endpoint, id), payload)
    item.value = data
    items.value = items.value.map((i) => (i.id === id ? data : i))
    return data
  }

  // Оптимистичное удаление: запись пропадает сразу и возвращается, если сервер отказал
  async function remove(id) {
    const snapshot = items.value
    items.value = items.value.filter((i) => i.id !== id)
    try {
      await client.delete(joinUrl(endpoint, id))
    } catch (err) {
      items.value = snapshot
      throw err
    }
  }

  return { items, item, isLoading, error, notFound, fetchList, fetchOne, create, update, remove }
}
