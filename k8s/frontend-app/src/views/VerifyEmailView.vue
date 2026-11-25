<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import client from '@/api/client'
import { errorMessage } from '@/api/errors'

const REDIRECT_SECONDS = 5
const route = useRoute()
const router = useRouter()
const state = ref('pending') // pending | success | error | resend
const waited = ref(0)
const countdown = ref(REDIRECT_SECONDS)
const error = ref('')
const email = ref('')
const resendState = ref('idle') // idle | sending | sent
let waitTimer = null
let redirectTimer = null

function stopTimers() {
  clearInterval(waitTimer)
  clearInterval(redirectTimer)
}

onMounted(async () => {
  const token = route.query.token
  if (!token) {
    state.value = 'resend'
    return
  }
  // Счётчик ожидания — только для пользователя; на запрос он не влияет
  waitTimer = setInterval(() => (waited.value += 1), 1000)
  try {
    await client.get('/auth/verify-email', { params: { token } })
    state.value = 'success'
    // Обратный отсчёт: пользователь успевает прочитать сообщение, затем — переход ко входу
    redirectTimer = setInterval(() => {
      countdown.value -= 1
      if (countdown.value <= 0) {
        clearInterval(redirectTimer)
        router.push({ name: 'login' })
      }
    }, 1000)
  } catch (err) {
    state.value = 'error'
    error.value =
      err?.response?.status === 400 ? 'Ссылка недействительна или устарела. Запросите новое письмо.' : errorMessage(err)
  } finally {
    clearInterval(waitTimer)
  }
})

// Таймеры живут дольше компонента, если их не остановить: переход по ссылке «Войти» до конца отсчёта
// иначе вызвал бы router.push уже с другой страницы
onUnmounted(stopTimers)

async function resend() {
  resendState.value = 'sending'
  try {
    await client.post('/auth/resend-verification', { email: email.value })
    resendState.value = 'sent'
  } catch (err) {
    resendState.value = 'idle'
    error.value = errorMessage(err)
  }
}
</script>

<template>
  <section class="card" aria-live="polite">
    <template v-if="state === 'pending'">
      <h1>Подтверждаем email…</h1>
      <p class="muted">Ожидание: {{ waited }} с</p>
    </template>
    <template v-else-if="state === 'success'">
      <p class="icon" aria-hidden="true">✅</p>
      <h1>Email подтверждён</h1>
      <p>Аккаунт активирован. Переход ко входу через {{ countdown }} с.</p>
      <RouterLink :to="{ name: 'login' }">Войти сейчас</RouterLink>
    </template>
    <template v-else>
      <h1>{{ state === 'error' ? 'Не удалось подтвердить email' : 'Подтверждение email' }}</h1>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <form v-if="resendState !== 'sent'" class="form" novalidate @submit.prevent="resend">
        <BaseInput v-model="email" label="Email, указанный при регистрации" type="email" autocomplete="email" />
        <BaseButton type="submit" :loading="resendState === 'sending'" :disabled="!email">Отправить письмо ещё раз</BaseButton>
      </form>
      <p v-else role="status">Если адрес зарегистрирован и не подтверждён, мы отправили новое письмо.</p>
    </template>
  </section>
</template>

<style scoped>
.card {
  max-width: 460px;
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
.muted {
  color: var(--color-muted);
}
.error {
  color: var(--color-danger);
}
.form {
  display: grid;
  gap: 14px;
  text-align: left;
}
</style>
