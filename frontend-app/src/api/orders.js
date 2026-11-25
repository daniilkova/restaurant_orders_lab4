import client from './client'

export async function fetchOrders(params = {}) {
  const { data } = await client.get('/orders/', { params: { limit: 100, ...params } })
  return data
}
