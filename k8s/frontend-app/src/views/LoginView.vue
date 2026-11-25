<script setup>
import { ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import { useAuthStore } from '@/stores/auth'
import { errorMessage } from '@/api/errors'
import { safeRedirect } from '@/router'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const step = ref('password') // password | code
const username = ref('')
const password = ref('')
const code = ref('')
const tempToken = ref('')
const isLoading = ref(false)
const error = ref('')
const notice = ref('')

function finish() {
  router.push(safeRedirect(route.query.redirect))
}

async function submitPassword() {
  if (isLoading.value) return
  error.value = ''
  notice.value = ''
  if (!username.value.trim() || !password.value) {
    error.value = 'Введите логин и пароль'
    return
  }
  isLoading.value = true
  try {
    const result = await auth.login(username.value.trim(), password.value)
    if (result.twoFactorRequired) {
      // Пароль верный, но вход ещё не выполнен: нужен код из приложения-аутентификатора
      tempToken.value = result.tempToken
      step.value = 'code'
    } else {
      finish()
    }
  } catch (err) {
    const detail = err?.response?.data?.detail
    if (detail === 'email_not_verified') {
      notice.value = 'Email ещё не подтверждён. Перейдите по ссылке из письма или запросите новое.'
    } else if (detail === 'age_verification_required') {
      notice.value = 'Для завершения регистрации подтвердите возраст.'
    } else {
      error.value = errorMessage(err, 'Не удалось войти')
    }
    password.value = ''
  } finally {
    isLoading.value = false
  }
}

async function submitCode() {
  if (isLoading.value) return
  error.value = ''
  if (!/^\d{6}$/.test(code.value)) {
    error.value = 'Введите 6 цифр из приложения'
    return
  }
  isLoading.value = true
  try {
    await auth.verifyTwoFactor(tempToken.value, code.value)
    finish()
  } catch (err) {
    error.value = err?.response?.status === 401 ? 'Неверный или устаревший код' : errorMessage(err)
    code.value = ''
    if (err?.response?.data?.detail === 'Invalid temporary token') step.value = 'password'
  } finally {
    isLoading.value = false
  }
}

function back() {
  step.value = 'password'
  code.value = ''
  error.value = ''
}
</script>

<template>
  <section class="auth-card">
    <template v-if="step === 'password'">
      <h1 class="auth-card__title">Вход</h1>
      <p class="auth-card__hint">Войдите, чтобы заказать и следить за заказами</p>
      <form class="auth-card__form" novalidate @submit.prevent="submitPassword">
        <BaseInput v-model="username" label="Логин" name="username" autocomplete="username" :disabled="isLoading" />
        <BaseInput
          v-model="password"
          label="Пароль"
          name="password"
          type="password"
          autocomplete="current-password"
          :disabled="isLoading"
        />
        <p v-if="error" class="auth-card__error" role="alert">{{ error }}</p>
        <p v-if="notice" class="auth-card__notice" role="status">
          {{ notice }}
          <RouterLink v-if="notice.startsWith('Email')" :to="{ name: 'verify-email' }">Отправить письмо ещё раз</RouterLink>
        </p>
        <BaseButton type="submit" block :loading="isLoading">Войти</BaseButton>
      </form>
      <p class="auth-card__footer">Нет аккаунта? <RouterLink :to="{ name: 'register' }">Зарегистрироваться</RouterLink></p>
    </template>

    <template v-else>
      <h1 class="auth-card__title">Код подтверждения</h1>
      <p class="auth-card__hint">Откройте приложение-аутентификатор и введите 6-значный код для «{{ username }}»</p>
      <form class="auth-card__form" novalidate @submit.prevent="submitCode">
        <BaseInput
          v-model="code"
          label="Код из приложения"
          name="code"
          inputmode="numeric"
          autocomplete="one-time-code"
          maxlength="6"
          :disabled="isLoading"
        />
        <p v-if="error" class="auth-card__error" role="alert">{{ error }}</p>
        <BaseButton type="submit" block :loading="isLoading">Подтвердить</BaseButton>
        <BaseButton variant="ghost" block :disabled="isLoading" @click="back">← Другой аккаунт</BaseButton>
      </form>
    </template>
  </section>
</template>

<style scoped>
.auth-card {
  max-width: 400px;
  margin: 32px auto;
  padding: 32px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
}
.auth-card__title {
  margin: 0;
  font-size: 26px;
}
.auth-card__hint {
  margin: 4px 0 24px;
  color: var(--color-muted);
}
.auth-card__form {
  display: grid;
  gap: 16px;
}
.auth-card__error,
.auth-card__notice {
  margin: 0;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  font-size: 14px;
}
.auth-card__error {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}
.auth-card__notice {
  background: #eef2ff;
  color: var(--color-info);
}
.auth-card__footer {
  margin: 20px 0 0;
  text-align: center;
  color: var(--color-muted);
}
</style>
