<script setup>
import { computed } from 'vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import { dishImageUrl } from '@/api/dishes'
import { formatMoney } from '@/utils/format'

const props = defineProps({ dish: { type: Object, required: true } })
const image = computed(() => dishImageUrl(props.dish))
</script>

<template>
  <BaseCard as="li" interactive class="dish" :class="{ 'dish--off': !dish.is_available }">
    <div class="dish__image" :class="{ 'dish__image--empty': !image }">
      <img v-if="image" :src="image" :alt="dish.name" loading="lazy" />
      <span v-else aria-hidden="true">🍽</span>
      <span v-if="!dish.is_available" class="dish__flag">Нет в продаже</span>
    </div>
    <h3 class="dish__name">
      <!-- ссылка растянута на всю карточку через ::after: карточка кликабельна и доступна с клавиатуры -->
      <RouterLink :to="{ name: 'dish-detail', params: { id: dish.id } }" class="dish__link">{{ dish.name }}</RouterLink>
    </h3>
    <p v-if="dish.description" class="dish__desc">{{ dish.description }}</p>
    <p class="dish__price">{{ formatMoney(dish.price) }}</p>
  </BaseCard>
</template>

<style scoped>
.dish :deep(.card__body) {
  padding: 0 0 16px;
  display: flex;
  flex-direction: column;
}
.dish__image {
  position: relative;
  aspect-ratio: 4 / 3;
  background: linear-gradient(135deg, #fde7d4, #fbd3b1);
  display: grid;
  place-items: center;
  font-size: 44px;
  overflow: hidden;
}
.dish__image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.dish__flag {
  position: absolute;
  top: 10px;
  left: 10px;
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(43, 33, 24, 0.8);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}
.dish--off .dish__image {
  filter: grayscale(0.7);
}
.dish__name {
  margin: 12px 16px 4px;
  font-size: 17px;
}
.dish__link {
  color: inherit;
  text-decoration: none;
}
.dish__link::after {
  content: '';
  position: absolute;
  inset: 0;
}
.dish__link:focus-visible {
  outline: none;
}
.dish:focus-within {
  box-shadow: var(--focus-ring), var(--shadow-lg);
}
.dish__desc {
  margin: 0 16px 8px;
  color: var(--color-muted);
  font-size: 14px;
}
.dish__price {
  margin: auto 16px 0;
  font-weight: 700;
  color: var(--color-primary);
}
</style>
