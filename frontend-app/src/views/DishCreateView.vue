<script setup>
import { useRouter } from 'vue-router'
import DishForm from '@/components/DishForm.vue'
import { useResource } from '@/composables/useResource'
import { useToast } from '@/composables/useToast'
import { toDishPayload } from '@/api/dishes'

const router = useRouter()
const toast = useToast()
const dishes = useResource('/dishes')

async function save(values) {
  const created = await dishes.create(toDishPayload(values))
  toast.success(`Блюдо «${created.name}» добавлено в меню`)
  router.push({ name: 'dish-detail', params: { id: created.id } })
}
</script>

<template>
  <section class="page">
    <h1>Новое блюдо</h1>
    <DishForm submit-label="Создать" :on-submit="save" @cancel="router.push({ name: 'home' })" />
  </section>
</template>

<style scoped>
.page {
  max-width: 560px;
  padding: 24px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}
h1 {
  margin-top: 0;
}
</style>
