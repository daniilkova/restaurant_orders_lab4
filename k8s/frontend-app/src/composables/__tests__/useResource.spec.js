import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/client', () => ({ default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }))

import client from '@/api/client'
import { useResource } from '../useResource'

describe('useResource', () => {
  beforeEach(() => vi.clearAllMocks())

  it('URL без двойного слэша', async () => {
    client.get.mockResolvedValue({ data: [] })
    const r = useResource('/dishes/')
    await r.fetchList()
    await r.fetchOne(5)
    expect(client.get.mock.calls.map((c) => c[0])).toEqual(['/dishes/', '/dishes/5'])
  })

  it('fetchList: загрузка и данные', async () => {
    client.get.mockResolvedValue({ data: [{ id: 1 }] })
    const r = useResource('/dishes')
    const promise = r.fetchList()
    expect(r.isLoading.value).toBe(true)
    await promise
    expect(r.isLoading.value).toBe(false)
    expect(r.items.value).toEqual([{ id: 1 }])
  })

  it('404 отличается от прочих ошибок', async () => {
    client.get.mockRejectedValueOnce({ response: { status: 404, data: { detail: 'Dish not found' } } })
    const r = useResource('/dishes')
    await r.fetchOne(9)
    expect(r.notFound.value).toBe(true)
    client.get.mockRejectedValueOnce(new Error('Network Error'))
    await r.fetchOne(9)
    expect(r.notFound.value).toBe(false)
    expect(r.error.value).toContain('Сервер недоступен')
  })

  it('ответ устаревшего запроса не перезаписывает новый', async () => {
    let resolveOld
    client.get
      .mockImplementationOnce(() => new Promise((r) => (resolveOld = r)))
      .mockResolvedValueOnce({ data: [{ id: 2 }] })
    const r = useResource('/dishes')
    const old = r.fetchList()
    await r.fetchList()
    resolveOld({ data: [{ id: 1 }] })
    await old
    expect(r.items.value).toEqual([{ id: 2 }])
  })

  it('оптимистичное удаление откатывается при ошибке', async () => {
    const r = useResource('/dishes')
    r.items.value = [{ id: 1 }, { id: 2 }]
    client.delete.mockRejectedValue({ response: { status: 409 } })
    const promise = r.remove(1)
    expect(r.items.value).toEqual([{ id: 2 }])
    await expect(promise).rejects.toBeTruthy()
    expect(r.items.value).toEqual([{ id: 1 }, { id: 2 }])
  })

  it('update заменяет запись в списке', async () => {
    const r = useResource('/dishes')
    r.items.value = [{ id: 1, name: 'A' }]
    client.put.mockResolvedValue({ data: { id: 1, name: 'B' } })
    await r.update(1, { name: 'B' })
    expect(r.items.value[0].name).toBe('B')
    expect(r.item.value.name).toBe('B')
  })
})
