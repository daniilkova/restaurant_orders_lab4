const money = new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 2 })
const dateTime = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })

export const formatMoney = (value) => money.format(value)
export const formatDateTime = (iso) => dateTime.format(new Date(iso))

export const STATUS_LABELS = {
  принят: 'Принят',
  готовится: 'Готовится',
  доставляется: 'Доставляется',
  завершён: 'Завершён',
}
