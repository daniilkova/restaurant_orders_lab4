import { beforeEach, describe, expect, it, vi } from 'vitest'
import client, { setUnauthorizedHandler } from '../client'

// Подменяем транспорт axios: запросы не уходят в сеть
const calls = []
let script = []
client.defaults.adapter = async (config) => {
  calls.push(config.url)
  const next = script.shift()
  if (next.status >= 400) {
    const error = new Error(`HTTP ${next.status}`)
    error.config = config
    error.response = { status: next.status, data: {} }
    throw error
  }
  return { status: next.status, data: next.data ?? {}, headers: {}, config }
}

describe('client: cookies и автоматическое продление сессии', () => {
  beforeEach(() => {
    calls.length = 0
    script = []
  })

  it('withCredentials и заголовок X-Requested-With', () => {
    expect(client.defaults.withCredentials).toBe(true)
    expect(client.defaults.headers['X-Requested-With']).toBe('XMLHttpRequest')
  })

  it('401 -> /auth/refresh -> повтор исходного запроса', async () => {
    script = [{ status: 401 }, { status: 204 }, { status: 200, data: [1] }]
    const { data } = await client.get('/orders/')
    expect(calls).toEqual(['/orders/', '/auth/refresh', '/orders/'])
    expect(data).toEqual([1])
  })

  it('refresh не удался — обработчик выхода', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    script = [{ status: 401 }, { status: 401 }]
    await expect(client.get('/orders/')).rejects.toThrow('HTTP 401')
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('401 на /auth/token — ответ по существу, без refresh', async () => {
    script = [{ status: 401 }]
    await expect(client.post('/auth/token', 'x')).rejects.toThrow('HTTP 401')
    expect(calls).toEqual(['/auth/token'])
  })
})
