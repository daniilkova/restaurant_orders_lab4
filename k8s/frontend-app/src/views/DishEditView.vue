<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import DishForm from '@/components/DishForm.vue'
import { useResource } from '@/composables/useResource'
import { useToast } from '@/composables/useToast'
import { toDishPayload } from '@/api/dishes'

const props = defineProps({ id: { type: [String, Number], required: true } })
const router = useRouter()
const toast = useToast()
const dishes = useResource('/dishes')

onMounted(() => dishes.fetchOne(Number(props.id)))

async function save(values) {
  try {
    const updated = await dishes.update(Number(props.id), toDishPayload(values))
    toast.success(`Изменения в «${updated.name}» сохранены`)
    router.push({ name: 'dish-detail', params: { id: updated.id } })
  } catch (err) {
    if (err?.response?.status === 404) {
      dishes.notFound.value = true
      toast.error('Блюдо уже удалено')
      return
    }
    throw err // 422 и прочее разберёт форма
  }
}
</script>

<template>
  <section class="page">
    <h1>Редактирование блюда</h1>
    <p v-if="dishes.isLoading.value" aria-live="polite">Загрузка…</p>
    <p v-else-if="dishes.notFound.value" class="error">Запись не найдена — возможно, её уже удалили.</p>
    <p v-else-if="dishes.error.value" class="error" role="alert">{{ dishes.error.value }}</p>
    <!-- форма появляется только после загрузки: иначе поля были бы пустыми -->
    <DishForm
      v-else-if="dishes.item.value"
      :initial-values="dishes.item.value"
      :on-submit="save"
      @cancel="router.push({ name: 'dish-detail', params: { id } })"
    />
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
.error {
  color: var(--color-danger);
}
</style>
