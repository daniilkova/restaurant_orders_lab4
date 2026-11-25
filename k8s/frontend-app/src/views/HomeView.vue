<script setup>
// Главный экран — меню ресторана. Данные и состояния — через useResource.
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import DishCard from '@/components/DishCard.vue'
import { useResource } from '@/composables/useResource'
import { useDebounced } from '@/composables/useDebouncedRef'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const dishes = useResource('/dishes')
const search = ref('')
const query = useDebounced(search, 300)

const hiddenAdult = computed(() => Number(dishes.headers.value['x-hidden-age-restricted'] || 0))

const visible = computed(() => {
  const q = query.value.trim().toLowerCase()
  const list = q
    ? dishes.items.value.filter((d) => `${d.name} ${d.description ?? ''}`.toLowerCase().includes(q))
    : dishes.items.value
  // в продаже — первыми
  return [...list].sort((a, b) => Number(b.is_available) - Number(a.is_available) || a.name.localeCompare(b.name))
})

onMounted(() => dishes.fetchList())
</script>

<template>
  <section>
    <div class="head">
      <div>
        <h1 class="head__title">Меню</h1>
        <p class="head__sub">Блюда, которые можно заказать с доставкой</p>
      </div>
      <BaseButton v-if="auth.isStaff" @click="router.push({ name: 'dish-create' })">+ Добавить</BaseButton>
    </div>

    <div class="toolbar">
      <BaseInput v-model="search" label="Поиск по меню" type="search" placeholder="Например, пицца" class="toolbar__search" />
    </div>

    <div v-if="hiddenAdult > 0" class="age-banner" role="note">
      <span>Ещё {{ hiddenAdult }} {{ hiddenAdult === 1 ? 'позиция' : 'позиции' }} 18+ скрыты.</span>
      <RouterLink :to="{ name: 'verify-age' }">Подтвердить возраст</RouterLink>
    </div>

    <p v-if="dishes.isLoading.value && !dishes.items.value.length" class="state" aria-live="polite">Загрузка меню…</p>
    <div v-else-if="dishes.error.value" class="state state--error" role="alert">
      <p>{{ dishes.error.value }}</p>
      <BaseButton variant="secondary" @click="dishes.fetchList()">Повторить</BaseButton>
    </div>
    <p v-else-if="!dishes.items.value.length" class="state">В меню пока нет блюд.</p>
    <p v-else-if="!visible.length" class="state">Ничего не найдено по запросу «{{ query }}».</p>
    <ul v-else class="grid">
      <DishCard v-for="dish in visible" :key="dish.id" :dish="dish" />
    </ul>
  </section>
</template>

<style scoped>
.head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.head__title {
  margin: 0;
  font-size: 28px;
}
.head__sub {
  margin: 4px 0 0;
  color: var(--color-muted);
}
.toolbar {
  margin-bottom: 20px;
  max-width: 360px;
}
.age-banner {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  align-items: center;
  margin-bottom: 16px;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  background: #eef2ff;
  color: var(--color-info);
}
.grid {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 18px;
}
.state {
  padding: 24px;
  border-radius: var(--radius-md);
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
</style>
