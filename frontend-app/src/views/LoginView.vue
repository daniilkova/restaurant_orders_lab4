<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { errorMessage } from '@/api/errors'
import { safeRedirect } from '@/router'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const isLoading = ref(false)
const error = ref('')

async function submit() {
  if (isLoading.value) return
  error.value = ''
  if (!username.value.trim() || !password.value) {
    error.value = 'Введите логин и пароль'
    return
  }
  isLoading.value = true
  try {
    await auth.login(username.value.trim(), password.value)
    router.push(safeRedirect(route.query.redirect))
  } catch (err) {
    error.value = errorMessage(err, 'Не удалось войти')
    password.value = ''
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <section class="login">
    <h1 class="login__title">Вход</h1>
    <p class="login__hint">Войдите, чтобы увидеть свои заказы</p>
    <form class="login__form" novalidate @submit.prevent="submit">
      <label class="field">
        <span class="field__label">Логин</span>
        <input v-model="username" name="username" autocomplete="username" :disabled="isLoading" />
      </label>
      <label class="field">
        <span class="field__label">Пароль</span>
        <input
          v-model="password"
          name="password"
          type="password"
          autocomplete="current-password"
          :disabled="isLoading"
        />
      </label>
      <p v-if="error" class="login__error" role="alert">{{ error }}</p>
      <button type="submit" class="login__submit" :disabled="isLoading">
        {{ isLoading ? 'Входим…' : 'Войти' }}
      </button>
    </form>
  </section>
</template>

<style scoped>
.login {
  max-width: 380px;
  margin: 40px auto;
  padding: 32px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}
.login__title {
  margin: 0;
  font-size: 26px;
}
.login__hint {
  margin: 4px 0 24px;
  color: var(--color-muted);
}
.login__form {
  display: grid;
  gap: 16px;
}
.field {
  display: grid;
  gap: 6px;
}
.field__label {
  font-size: 14px;
  font-weight: 600;
}
.field input {
  padding: 10px 12px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: #fff;
}
.field input:focus {
  border-color: var(--color-primary);
}
.login__error {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--color-danger-soft);
  color: var(--color-danger);
  font-size: 14px;
}
.login__submit {
  padding: 11px;
  border: none;
  border-radius: 8px;
  background: var(--color-primary);
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}
.login__submit:hover:not(:disabled) {
  background: var(--color-primary-hover);
}
.login__submit:disabled {
  opacity: 0.7;
  cursor: progress;
}
</style>
