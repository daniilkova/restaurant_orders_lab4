<script setup>
// Если профиль (/auth/me) недоступен, карточка просто не показывается: это вспомогательная
// функция, и ошибка здесь не должна пугать пользователя на странице безопасности
import { computed, ref } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import { startAgeVerification } from '@/api/age'
import { errorMessage } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const verified = computed(() => auth.user?.is_age_verified)
const loading = ref(false)
const error = ref('')

async function start() {
  loading.value = true
  error.value = ''
  try {
    await startAgeVerification()
  } catch (err) {
    error.value = errorMessage(err, 'Не удалось начать верификацию. Попробуйте позже.')
    loading.value = false
  }
}
</script>

<template>
  <BaseCard v-if="auth.user" as="article" class="sec-card">
    <div class="head">
      <h3>Возрастная верификация</h3>
      <span class="status" :class="{ 'status--on': verified }">{{ verified ? 'Пройдена' : 'Не пройдена' }}</span>
    </div>
    <p class="muted">
      Нужна, чтобы видеть и заказывать позиции 18+ (вино, пиво). Проверка через Self: мы получаем только
      факт «старше 18», без даты рождения.
    </p>
    <BaseButton v-if="!verified" :loading="loading" @click="start">Подтвердить возраст</BaseButton>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
  </BaseCard>
</template>

<style scoped>
.head { display: flex; align-items: center; justify-content: space-between; }
h3 { margin: 0; }
.status { padding: 2px 10px; border-radius: 999px; background: var(--color-secondary); color: var(--color-muted); font-size: 13px; font-weight: 600; }
.status--on { background: #ecfdf3; color: var(--color-success); }
.muted { margin: 6px 0 14px; color: var(--color-muted); font-size: 14px; }
.error { color: var(--color-danger); }
</style>
