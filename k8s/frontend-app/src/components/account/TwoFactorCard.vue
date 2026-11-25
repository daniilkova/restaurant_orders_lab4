<script setup>
import { computed, ref } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import client from '@/api/client'
import { errorMessage } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'

const auth = useAuthStore()
const toast = useToast()
const enabled = computed(() => auth.user?.totp_enabled)
const setup = ref(null) // { secret, qr_svg }
const code = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)
const disabling = ref(false)

async function begin() {
  busy.value = true
  error.value = ''
  try {
    setup.value = (await client.post('/auth/2fa/enable')).data
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    busy.value = false
  }
}

async function confirm() {
  if (!/^\d{6}$/.test(code.value)) {
    error.value = 'Введите 6 цифр из приложения'
    return
  }
  busy.value = true
  error.value = ''
  try {
    auth.user = (await client.post('/auth/2fa/confirm', { code: code.value })).data
    setup.value = null
    code.value = ''
    toast.success('Двухфакторная аутентификация включена')
  } catch (err) {
    error.value = err?.response?.status === 400 ? 'Неверный код. Проверьте время на телефоне и попробуйте ещё раз' : errorMessage(err)
  } finally {
    busy.value = false
  }
}

async function disable() {
  busy.value = true
  error.value = ''
  try {
    auth.user = (await client.post('/auth/2fa/disable', { password: password.value, code: code.value })).data
    disabling.value = false
    password.value = ''
    code.value = ''
    toast.info('Двухфакторная аутентификация отключена')
  } catch (err) {
    const field = err?.response?.data?.detail?.field
    error.value = field === 'password' ? 'Неверный пароль' : field === 'code' ? 'Неверный код' : errorMessage(err)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <BaseCard as="article" class="sec-card">
    <div class="head">
      <h3>Двухфакторная аутентификация</h3>
      <span class="status" :class="{ 'status--on': enabled }">{{ enabled ? 'Включена' : 'Выключена' }}</span>
    </div>
    <p class="muted">При входе, кроме пароля, понадобится 6-значный код из приложения (Google Authenticator, Яндекс Ключ, Aegis).</p>

    <template v-if="!enabled && !setup">
      <BaseButton :loading="busy" @click="begin">Включить 2FA</BaseButton>
    </template>

    <div v-else-if="!enabled && setup" class="setup">
      <img :src="setup.qr_svg" width="180" height="180" alt="QR-код для приложения-аутентификатора" class="qr" />
      <div class="setup__form">
        <p>1. Отсканируйте QR-код. Или введите ключ вручную:</p>
        <code class="secret">{{ setup.secret }}</code>
        <p>2. Введите код из приложения:</p>
        <BaseInput v-model="code" label="Код" inputmode="numeric" maxlength="6" autocomplete="one-time-code" :error="error" />
        <div class="row">
          <BaseButton :loading="busy" @click="confirm">Подтвердить</BaseButton>
          <BaseButton variant="ghost" :disabled="busy" @click="setup = null">Отмена</BaseButton>
        </div>
      </div>
    </div>

    <template v-else>
      <BaseButton v-if="!disabling" variant="secondary" @click="disabling = true">Отключить 2FA</BaseButton>
      <form v-else class="disable" @submit.prevent="disable">
        <BaseInput v-model="password" label="Пароль" type="password" autocomplete="current-password" />
        <BaseInput v-model="code" label="Код из приложения" inputmode="numeric" maxlength="6" />
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <div class="row">
          <BaseButton type="submit" variant="danger" :loading="busy">Отключить</BaseButton>
          <BaseButton variant="ghost" @click="disabling = false">Отмена</BaseButton>
        </div>
      </form>
    </template>
    <p v-if="error && !setup && !disabling" class="error" role="alert">{{ error }}</p>
  </BaseCard>
</template>

<style scoped>
.head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
h3 { margin: 0; }
.status { padding: 2px 10px; border-radius: 999px; background: var(--color-secondary); color: var(--color-muted); font-size: 13px; font-weight: 600; }
.status--on { background: #ecfdf3; color: var(--color-success); }
.muted { margin: 6px 0 14px; color: var(--color-muted); font-size: 14px; }
.setup { display: flex; flex-wrap: wrap; gap: 20px; }
.qr { border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: #fff; }
.setup__form { flex: 1; min-width: 220px; display: grid; gap: 8px; }
.setup__form p { margin: 0; }
.secret { padding: 6px 10px; background: var(--color-secondary); border-radius: var(--radius-sm); word-break: break-all; }
.row { display: flex; gap: 8px; margin-top: 6px; }
.disable { display: grid; gap: 10px; max-width: 320px; }
.error { margin: 0; color: var(--color-danger); }
</style>
