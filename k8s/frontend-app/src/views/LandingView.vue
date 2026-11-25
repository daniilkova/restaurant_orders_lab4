<script setup>
import { useRouter } from 'vue-router'
import BaseButton from '@/components/ui/BaseButton.vue'

const router = useRouter()
const FEATURES = [
  { icon: '🍕', title: 'Меню с фото', text: 'Пицца, роллы, супы и десерты — с ценами и составом.' },
  { icon: '🛵', title: 'Статус в реальном времени', text: 'Принят → готовится → доставляется → завершён.' },
  { icon: '🔒', title: 'Безопасный аккаунт', text: 'Подтверждение email, двухфакторный вход, управление сессиями.' },
]
</script>

<template>
  <section class="landing">
    <div class="hero">
      <p class="hero__eyebrow">Доставка из ресторана «Пряность»</p>
      <h1 class="hero__title">Горячая еда — к вашей двери за 40 минут</h1>
      <p class="hero__text">Войдите, чтобы заказать из меню и следить за статусом заказа.</p>
      <div class="hero__actions">
        <BaseButton size="lg" @click="router.push({ name: 'login' })">Войти</BaseButton>
        <BaseButton size="lg" variant="secondary" @click="router.push({ name: 'register' })">Зарегистрироваться</BaseButton>
      </div>
    </div>
    <ul class="features">
      <li v-for="f in FEATURES" :key="f.title" class="feature">
        <span class="feature__icon" aria-hidden="true">{{ f.icon }}</span>
        <h2 class="feature__title">{{ f.title }}</h2>
        <p class="feature__text">{{ f.text }}</p>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.hero {
  padding: 48px 32px;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, #fff1e6 0%, #fde2c8 100%);
  text-align: center;
}
.hero__eyebrow {
  margin: 0 0 8px;
  color: var(--color-primary);
  font-weight: 600;
}
.hero__title {
  margin: 0 auto 12px;
  max-width: 640px;
  font-size: clamp(28px, 5vw, 42px);
  line-height: 1.15;
}
.hero__text {
  margin: 0 0 24px;
  color: var(--color-muted);
}
.hero__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
}
.features {
  list-style: none;
  padding: 0;
  margin: 28px 0 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}
.feature {
  padding: 20px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}
.feature__icon {
  font-size: 28px;
}
.feature__title {
  margin: 8px 0 4px;
  font-size: 18px;
}
.feature__text {
  margin: 0;
  color: var(--color-muted);
}
</style>
