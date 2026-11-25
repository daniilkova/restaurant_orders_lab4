<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import { useResource } from '@/composables/useResource'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'
import { dishImageUrl, uploadDishImage } from '@/api/dishes'
import { errorMessage } from '@/api/errors'
import { formatMoney } from '@/utils/format'

const props = defineProps({ id: { type: [String, Number], required: true } })
const router = useRouter()
const toast = useToast()
const auth = useAuthStore()
const dishes = useResource('/dishes')
const dish = dishes.item

const confirmOpen = ref(false)
const isDeleting = ref(false)
const isUploading = ref(false)
const fileInput = ref(null)
const image = computed(() => dishImageUrl(dish.value))

onMounted(() => dishes.fetchOne(Number(props.id)))

async function confirmDelete() {
  isDeleting.value = true
  try {
    await dishes.remove(Number(props.id))
    confirmOpen.value = false
    toast.success(`Блюдо «${dish.value.name}» удалено`)
    router.push({ name: 'home' })
  } catch (err) {
    toast.error(errorMessage(err, 'Не удалось удалить блюдо'))
  } finally {
    isDeleting.value = false
  }
}

async function onFileChange(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  isUploading.value = true
  try {
    dish.value = await uploadDishImage(Number(props.id), file)
    toast.success('Фото обновлено')
  } catch (err) {
    toast.error(errorMessage(err, 'Не удалось загрузить фото'))
  } finally {
    isUploading.value = false
  }
}
</script>

<template>
  <section class="detail">
    <RouterLink to="/" class="back">← Меню</RouterLink>

    <p v-if="dishes.isLoading.value" class="state" aria-live="polite">Загрузка…</p>
    <div v-else-if="dishes.notFound.value" class="state">
      <h1>Запись не найдена</h1>
      <p>Возможно, блюдо уже удалили.</p>
    </div>
    <div v-else-if="dishes.error.value" class="state state--error" role="alert">{{ dishes.error.value }}</div>

    <article v-else-if="dish" class="card">
      <div class="card__image" :class="{ 'card__image--empty': !image }">
        <img v-if="image" :src="image" :alt="dish.name" />
        <span v-else aria-hidden="true">🍽</span>
      </div>
      <div class="card__info">
        <h1 class="card__title">{{ dish.name }}</h1>
        <dl class="props">
          <dt>Описание</dt>
          <dd>{{ dish.description || '—' }}</dd>
          <dt>Цена</dt>
          <dd class="price">{{ formatMoney(dish.price) }}</dd>
          <dt>Наличие</dt>
          <dd>{{ dish.is_available ? 'В продаже' : 'Нет в продаже' }}</dd>
        </dl>
        <div v-if="auth.isAdmin" class="actions">
          <BaseButton variant="secondary" @click="router.push({ name: 'dish-edit', params: { id: dish.id } })">
            Редактировать
          </BaseButton>
          <BaseButton variant="secondary" :loading="isUploading" @click="fileInput.click()">
            {{ image ? 'Заменить фото' : 'Загрузить фото' }}
          </BaseButton>
          <input
            ref="fileInput"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            class="visually-hidden"
            tabindex="-1"
            aria-hidden="true"
            @change="onFileChange"
          />
          <BaseButton variant="danger" @click="confirmOpen = true">Удалить</BaseButton>
        </div>
      </div>
    </article>

    <BaseModal :open="confirmOpen" title="Удалить блюдо?" :persistent="isDeleting" @close="confirmOpen = false">
      <p>«{{ dish?.name }}» исчезнет из меню. Это действие нельзя отменить.</p>
      <template #actions>
        <BaseButton variant="secondary" data-autofocus :disabled="isDeleting" @click="confirmOpen = false">Отмена</BaseButton>
        <BaseButton variant="danger" :loading="isDeleting" @click="confirmDelete">Удалить</BaseButton>
      </template>
    </BaseModal>
  </section>
</template>

<style scoped>
.back {
  display: inline-block;
  margin-bottom: 16px;
  text-decoration: none;
  font-weight: 500;
}
.card {
  display: grid;
  grid-template-columns: minmax(240px, 420px) 1fr;
  gap: 28px;
  padding: 24px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.card__image {
  aspect-ratio: 4 / 3;
  border-radius: var(--radius-md);
  overflow: hidden;
  display: grid;
  place-items: center;
  font-size: 64px;
  background: linear-gradient(135deg, #fde7d4, #fbd3b1);
}
.card__image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.card__title {
  margin: 0 0 16px;
  font-size: 28px;
}
.props {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 10px 16px;
  margin: 0 0 24px;
}
.props dt {
  color: var(--color-muted);
}
.props dd {
  margin: 0;
}
.price {
  font-weight: 700;
  color: var(--color-primary);
  font-size: 20px;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
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
  color: var(--color-danger);
  background: var(--color-danger-soft);
}
@media (max-width: 720px) {
  .card {
    grid-template-columns: 1fr;
  }
}
</style>
