<script setup>
import { computed, onMounted, ref } from 'vue'
import { fetchOrders } from '@/api/orders'
import { errorMessage } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'
import { STATUS_LABELS, formatDateTime, formatMoney } from '@/utils/format'

const auth = useAuthStore()
const orders = ref([])
const isLoading = ref(true)
const error = ref('')

const title = computed(() => (auth.isAdmin ? 'Все заказы' : 'Мои заказы'))
const activeCount = computed(() => orders.value.filter((o) => o.status !== 'завершён').length)

async function load() {
  isLoading.value = true
  error.value = ''
  try {
    // Новые заказы сверху
    orders.value = (await fetchOrders()).slice().sort((a, b) => b.id - a.id)
  } catch (err) {
    error.value = errorMessage(err, 'Не удалось загрузить заказы')
  } finally {
    isLoading.value = false
  }
}

// Данные грузим после монтирования: компонент уже на странице и показывает «Загрузка…»
onMounted(load)
</script>

<template>
  <section>
    <div class="head">
      <div>
        <h1 class="head__title">{{ title }}</h1>
        <p v-if="!isLoading && !error" class="head__sub">
          Всего {{ orders.length }}, активных {{ activeCount }}
        </p>
      </div>
      <button type="button" class="refresh" :disabled="isLoading" @click="load">Обновить</button>
    </div>

    <p v-if="isLoading" class="state" aria-live="polite">Загрузка заказов…</p>

    <div v-else-if="error" class="state state--error" role="alert">
      <p>{{ error }}</p>
      <button type="button" class="refresh" @click="load">Повторить</button>
    </div>

    <p v-else-if="orders.length === 0" class="state">Заказов пока нет.</p>

    <ul v-else class="orders">
      <li v-for="order in orders" :key="order.id" class="order">
        <div class="order__top">
          <span class="order__id">Заказ №{{ order.id }}</span>
          <span class="badge" :class="`badge--${order.status}`">{{ STATUS_LABELS[order.status] }}</span>
        </div>
        <p class="order__date">{{ formatDateTime(order.created_at) }}</p>
        <ul class="items">
          <li v-for="item in order.items" :key="item.dish_id" class="items__row">
            <span>{{ item.dish_name }} × {{ item.quantity }}</span>
            <span>{{ formatMoney(item.subtotal) }}</span>
          </li>
        </ul>
        <div class="order__total">
          <span>Итого</span>
          <strong>{{ formatMoney(order.total) }}</strong>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}
.head__title {
  margin: 0;
  font-size: 28px;
}
.head__sub {
  margin: 4px 0 0;
  color: var(--color-muted);
}
.refresh {
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  border-radius: 8px;
  padding: 8px 16px;
  cursor: pointer;
}
.refresh:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.state {
  padding: 24px;
  border-radius: var(--radius);
  background: var(--color-surface);
  border: 1px dashed var(--color-border);
  color: var(--color-muted);
  text-align: center;
}
.state--error {
  border-style: solid;
  border-color: #f5c2c2;
  background: var(--color-danger-soft);
  color: var(--color-danger);
}
.orders {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}
.order {
  padding: 18px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}
.order__top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.order__id {
  font-weight: 700;
}
.order__date {
  margin: 2px 0 12px;
  color: var(--color-muted);
  font-size: 14px;
}
.items {
  list-style: none;
  padding: 0;
  margin: 0 0 12px;
  display: grid;
  gap: 4px;
  font-size: 15px;
}
.items__row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}
.order__total {
  display: flex;
  justify-content: space-between;
  padding-top: 10px;
  border-top: 1px solid var(--color-border);
}
.badge {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
}
.badge--принят {
  background: #eef2ff;
  color: var(--color-info);
}
.badge--готовится {
  background: #fff7e6;
  color: #b45309;
}
.badge--доставляется {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.badge--завершён {
  background: #ecfdf3;
  color: var(--color-success);
}
</style>
