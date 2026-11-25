import client from './client'

const FIELDS = ['name', 'description', 'price', 'is_available']

// В PUT/POST уходят только поля блюда: id, image_url и т.п. бэкенд отклонит (extra="forbid")
export function toDishPayload(values) {
  const payload = Object.fromEntries(FIELDS.map((f) => [f, values[f]]))
  payload.description = payload.description?.trim() ? payload.description.trim() : null
  payload.name = payload.name?.trim()
  return payload
}

export async function uploadDishImage(id, file) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await client.put(`/dishes/${id}/image`, form)
  return data
}

export function dishImageUrl(dish) {
  if (!dish?.image_url) return null
  const base = client.defaults.baseURL?.replace(/\/$/, '') ?? ''
  return `${base}${dish.image_url}`
}
