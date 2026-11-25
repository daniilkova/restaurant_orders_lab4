<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import BaseButton from '@/components/ui/BaseButton.vue'
import { REGISTRATION_TOKEN_KEY, completeRegistration, startAgeVerification } from '@/api/age'
import { errorMessage } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'

const route = useRoute()
const auth = useAuthStore()
const toast = useToast()
const isRegistration = computed(() => route.query.registration === 'true')
const outcome = computed(() => route.query.age)
const state = ref('intro') // intro | email-sent | verified | failed
const sentTo = ref('')
const isLoading = ref(false)
const error = ref('')

async function start() {
  isLoading.value = true
  error.value = ''
  try {
    await startAgeVerification(isRegistration.value ? sessionStorage.getItem(REGISTRATION_TOKEN_KEY) : null)
  } catch (err) {
    error.value = errorMessage(err, 'Не удалось начать верификацию. Попробуйте позже.')
    isLoading.value = false
  }
}

onMounted(async () => {
  if (outcome.value === 'failure') {
    state.value = 'failed'
    toast.error('Не удалось подтвердить возраст')
    return
  }
  if (outcome.value !== 'success') return
  if (isRegistration.value) {
    // Регистрация продолжается только после проверки возраста: теперь отправляем письмо
    try {
      const result = await completeRegistration(sessionStorage.getItem(REGISTRATION_TOKEN_KEY))
      sessionStorage.removeItem(REGISTRATION_TOKEN_KEY)
      sentTo.value = result.email
      state.value = 'email-sent'
      toast.success('Возраст подтверждён')
    } catch (err) {
      state.value = 'failed'
      error.value = errorMessage(err)
    }
  } else {
    await auth.fetchMe().catch(() => {})
    state.value = 'verified'
    toast.success('Возраст подтверждён')
  }
})
</script>

<template>
  <section class="card" aria-live="polite">
    <template v-if="state === 'email-sent'">
      <p class="icon" aria-hidden="true">✉️</p>
      <h1>Возраст подтверждён — проверьте почту</h1>
      <p>Последний шаг: перейдите по ссылке из письма, отправленного на <b>{{ sentTo }}</b>.</p>
    </template>
    <template v-else-if="state === 'verified'">
      <p class="icon" aria-hidden="true">✅</p>
      <h1>Возраст подтверждён</h1>
      <p>Теперь в меню доступны позиции 18+.</p>
      <RouterLink :to="{ name: 'home' }">К меню</RouterLink>
    </template>
    <template v-else>
      <h1>Подтверждение возраста</h1>
      <p v-if="state === 'failed'" class="error" role="alert">{{ error || 'Подтвердить возраст не удалось.' }}</p>
      <p>
        Мы используем <b>Self</b>: приложение доказывает, что вам больше 18 лет, с помощью zero-knowledge proof.
        Дату рождения и данные паспорта мы не получаем и не храним — только результат «старше 18».
      </p>
      <p v-if="error && state !== 'failed'" class="error" role="alert">{{ error }}</p>
      <BaseButton :loading="isLoading" @click="start">
        {{ state === 'failed' ? 'Попробовать ещё раз' : 'Подтвердить возраст' }}
      </BaseButton>
    </template>
  </section>
</template>

<style scoped>
.card {
  max-width: 520px;
  margin: 32px auto;
  padding: 32px;
  text-align: center;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}
.icon {
  font-size: 44px;
  margin: 0;
}
.error {
  color: var(--color-danger);
}
</style>
