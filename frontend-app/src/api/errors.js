// Понятные сообщения об ошибках HTTP для интерфейса
export function errorMessage(error, fallback = 'Что-то пошло не так') {
  if (!error?.response) {
    return 'Сервер недоступен. Проверьте, что бэкенд запущен, и повторите попытку.'
  }
  const { status, data } = error.response
  if (typeof data?.detail === 'string' && status < 500) {
    const known = {
      'Incorrect username or password': 'Неверный логин или пароль',
      'Too many failed login attempts, try again later': 'Слишком много неудачных попыток входа. Попробуйте позже.',
      'Order not found': 'Заказ не найден',
    }
    return known[data.detail] || data.detail
  }
  if (status === 401) return 'Сессия истекла, войдите снова'
  if (status === 403) return 'Недостаточно прав'
  if (status === 404) return 'Не найдено'
  if (status === 429) return 'Слишком много запросов, подождите немного'
  if (status >= 500) return 'Ошибка сервера. Попробуйте позже.'
  return fallback
}
