<script setup>
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import client from '@/api/client'
import { useForm } from '@/composables/useForm'
import { useToast } from '@/composables/useToast'

const toast = useToast()
const validators = {
  current_password: (v) => (!v ? 'Введите текущий пароль' : ''),
  new_password: (v) => (v.length < 8 ? 'Минимум 8 символов' : !/\d/.test(v) || !/\D/.test(v) ? 'Нужны буквы и цифры' : ''),
  confirm: (v, all) => (v !== all.new_password ? 'Пароли не совпадают' : ''),
}
const form = useForm({ current_password: '', new_password: '', confirm: '' }, validators, async (values) => {
  try {
    await client.post('/auth/change-password', {
      current_password: values.current_password,
      new_password: values.new_password,
    })
  } catch (err) {
    const detail = err?.response?.data?.detail
    if (err?.response?.status === 400 && detail?.field) {
      form.errors[detail.field] = detail.field === 'current_password' ? 'Неверный текущий пароль' : 'Новый пароль совпадает с текущим'
      return
    }
    throw err
  }
  form.reset()
  toast.success('Пароль изменён. Другие устройства вышли из аккаунта')
})
</script>

<template>
  <BaseCard as="article" class="sec-card">
    <h3>Смена пароля</h3>
    <p class="muted">Текущий пароль нужен, даже если вы уже вошли: так украденная сессия не сможет сменить пароль.</p>
    <form class="form" novalidate @submit.prevent="form.submit">
      <BaseInput v-model="form.values.current_password" label="Текущий пароль" type="password" autocomplete="current-password" :error="form.errors.current_password" />
      <BaseInput v-model="form.values.new_password" label="Новый пароль" type="password" autocomplete="new-password" :error="form.errors.new_password" />
      <BaseInput v-model="form.values.confirm" label="Повторите новый пароль" type="password" autocomplete="new-password" :error="form.errors.confirm" />
      <p v-if="form.submitError.value" class="error" role="alert">{{ form.submitError.value }}</p>
      <BaseButton type="submit" :loading="form.isSubmitting.value">Сменить пароль</BaseButton>
    </form>
  </BaseCard>
</template>

<style scoped>
h3 { margin: 0 0 4px; }
.muted { margin: 0 0 14px; color: var(--color-muted); font-size: 14px; }
.form { display: grid; gap: 12px; max-width: 380px; justify-items: start; }
.form :deep(.field) { width: 100%; }
.error { margin: 0; color: var(--color-danger); }
</style>
