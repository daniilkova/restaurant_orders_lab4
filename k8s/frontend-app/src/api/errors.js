// Разбор ошибок FastAPI для интерфейса
const KNOWN_DETAILS = {
  'Incorrect username or password': 'Неверный логин или пароль',
  'Too many failed login attempts, try again later': 'Слишком много неудачных попыток входа. Попробуйте позже.',
  'Order not found': 'Заказ не найден',
  'Dish not found': 'Блюдо не найдено',
  'Dish is used in orders; set is_available=false instead of deleting':
    'Блюдо уже есть в заказах — удалить нельзя. Снимите его с продажи.',
  'Insufficient privileges': 'Недостаточно прав для этого действия',
  'Only JPEG, PNG or WebP images are allowed': 'Можно загрузить только JPEG, PNG или WebP',
  age_verification_required: 'Нужна возрастная верификация (18+)',
  email_not_verified: 'Email не подтверждён',
  'Age verification is not configured': 'Возрастная верификация пока не настроена на сервере',
}

export function errorMessage(error, fallback = 'Что-то пошло не так') {
  if (!error?.response) {
    return 'Сервер недоступен. Проверьте, что бэкенд запущен, и повторите попытку.'
  }
  const { status, data } = error.response
  if (typeof data?.detail === 'string' && status < 500) {
    return KNOWN_DETAILS[data.detail] || data.detail
  }
  if (status === 401) return 'Сессия истекла, войдите снова'
  if (status === 403) return 'Недостаточно прав для этого действия'
  if (status === 404) return 'Запись не найдена'
  if (status === 409) return 'Конфликт данных: запись изменилась или используется'
  if (status === 413) return 'Файл слишком большой'
  if (status === 422) return 'Проверьте правильность заполнения полей'
  if (status === 429) return 'Слишком много запросов, подождите немного'
  if (status >= 500) return 'Ошибка сервера. Попробуйте позже.'
  return fallback
}

// Ошибки Pydantic v2 по-русски (type + ctx), иначе — исходный текст
function translate(err) {
  const ctx = err.ctx || {}
  switch (err.type) {
    case 'missing':
      return 'Обязательное поле'
    case 'string_too_short':
      return `Минимум ${ctx.min_length} символов`
    case 'string_too_long':
      return `Не больше ${ctx.max_length} символов`
    case 'greater_than':
      return `Значение должно быть больше ${ctx.gt}`
    case 'greater_than_equal':
      return `Значение должно быть не меньше ${ctx.ge}`
    case 'less_than_equal':
      return `Значение должно быть не больше ${ctx.le}`
    case 'less_than':
      return `Значение должно быть меньше ${ctx.lt}`
    case 'float_parsing':
    case 'int_parsing':
      return 'Введите число'
    case 'extra_forbidden':
      return 'Лишнее поле'
    default:
      return err.msg
  }
}

/**
 * 422 FastAPI -> { fieldErrors: { name: 'текст' }, general: 'текст' | '' }.
 * loc = ['body', 'price'] — второй элемент и есть имя поля формы.
 */
export function parseValidationError(error, knownFields = []) {
  const result = { fieldErrors: {}, general: '' }
  const detail = error?.response?.data?.detail
  if (error?.response?.status !== 422 || !Array.isArray(detail)) return result
  for (const err of detail) {
    const field = Array.isArray(err.loc) && err.loc[0] === 'body' ? err.loc[1] : undefined
    const message = translate(err)
    if (field && knownFields.includes(field)) {
      result.fieldErrors[field] ??= message
    } else {
      result.general = result.general ? `${result.general}; ${message}` : message
    }
  }
  return result
}
