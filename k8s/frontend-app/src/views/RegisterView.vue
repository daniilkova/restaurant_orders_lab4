<script setup>
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import { useForm } from '@/composables/useForm'
import { useAuthStore } from '@/stores/auth'
import { REGISTRATION_TOKEN_KEY } from '@/api/age'

const auth = useAuthStore()
const router = useRouter()
const sentTo = ref('')

const validators = {
  username: (v) => (!/^[A-Za-z0-9_.-]{3,50}$/.test(v) ? '3–50 символов: латинские буквы, цифры, . _ -' : ''),
  email: (v) => (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) ? 'Введите корректный email' : ''),
  password: (v, all) =>
    v.length < 8
      ? 'Минимум 8 символов'
      : !/\d/.test(v) || !/[A-Za-zА-Яа-яЁё]/.test(v)
        ? 'Нужны буквы и цифры'
        : all.username && v.toLowerCase().includes(all.username.toLowerCase())
          ? 'Пароль не должен содержать логин'
          : '',
  confirm: (v, all) => (v !== all.password ? 'Пароли не совпадают' : ''),
}

const form = useForm({ username: '', email: '', password: '', confirm: '' }, validators, async (values) => {
  try {
    const result = await auth.register({ username: values.username, email: values.email, password: values.password })
    if (result.requires_age_verification) {
      // Короткоживущий (30 мин) токен регистрации — до возвращения со страницы Self
      sessionStorage.setItem(REGISTRATION_TOKEN_KEY, result.registration_token)
      router.push({ name: 'verify-age', query: { registration: 'true' } })
    } else {
      sentTo.value = result.email
    }
  } catch (err) {
    const detail = err?.response?.data?.detail
    if (err?.response?.status === 409 && detail?.field) {
      // 409: логин или email заняты — ошибка под соответствующим полем
      form.errors[detail.field] = detail.field === 'email' ? 'Этот email уже зарегистрирован' : 'Этот логин уже занят'
      return
    }
    throw err
  }
})
</script>

<template>
  <section class="auth-card">
    <template v-if="!sentTo">
      <h1 class="auth-card__title">Регистрация</h1>
      <p class="auth-card__hint">После регистрации придёт письмо для подтверждения email</p>
      <form class="auth-card__form" novalidate @submit.prevent="form.submit">
        <BaseInput v-model="form.values.username" label="Логин" name="username" autocomplete="username" required
          :error="form.errors.username" @blur="form.validateField('username')" />
        <BaseInput v-model="form.values.email" label="Email" name="email" type="email" autocomplete="email" required
          :error="form.errors.email" @blur="form.validateField('email')" />
        <BaseInput v-model="form.values.password" label="Пароль" name="password" type="password"
          autocomplete="new-password" hint="Не меньше 8 символов, буквы и цифры" required
          :error="form.errors.password" @blur="form.validateField('password')" />
        <BaseInput v-model="form.values.confirm" label="Повторите пароль" name="confirm" type="password"
          autocomplete="new-password" required :error="form.errors.confirm" @blur="form.validateField('confirm')" />
        <p v-if="form.submitError.value" class="auth-card__error" role="alert">{{ form.submitError.value }}</p>
        <BaseButton type="submit" block :loading="form.isSubmitting.value">Создать аккаунт</BaseButton>
      </form>
      <p class="auth-card__footer">Уже есть аккаунт? <RouterLink :to="{ name: 'login' }">Войти</RouterLink></p>
    </template>
    <div v-else class="done" role="status">
      <p class="done__icon" aria-hidden="true">✉️</p>
      <h1 class="auth-card__title">Проверьте почту</h1>
      <p>Мы отправили ссылку для подтверждения на <b>{{ sentTo }}</b>. После подтверждения можно войти.</p>
      <RouterLink :to="{ name: 'login' }">Перейти ко входу</RouterLink>
    </div>
  </section>
</template>

<style scoped>
.auth-card {
  max-width: 420px;
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
.auth-card__error {
  margin: 0;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: var(--color-danger-soft);
  color: var(--color-danger);
}
.auth-card__footer {
  margin: 20px 0 0;
  text-align: center;
  color: var(--color-muted);
}
.done {
  text-align: center;
}
.done__icon {
  font-size: 44px;
  margin: 0;
}
</style>
