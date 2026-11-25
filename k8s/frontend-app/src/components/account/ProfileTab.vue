<script setup>
import { computed, ref } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import client from '@/api/client'
import { errorMessage } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'

const auth = useAuthStore()
const toast = useToast()
const user = computed(() => auth.user)
const ROLE_LABELS = { admin: 'Администратор', moderator: 'Модератор', client: 'Клиент' }

const displayName = ref(user.value.display_name || '')
const username = ref(user.value.username)
const savingName = ref(false)
const savingUsername = ref(false)
const uploading = ref(false)
const usernameError = ref('')
const fileInput = ref(null)

const nextChange = computed(() => (user.value.next_username_change_at ? new Date(user.value.next_username_change_at) : null))
const usernameLocked = computed(() => nextChange.value && nextChange.value > new Date())

async function saveName() {
  savingName.value = true
  try {
    auth.user = (await client.patch('/users/me', { display_name: displayName.value })).data
    toast.success('Имя сохранено')
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    savingName.value = false
  }
}

async function saveUsername() {
  usernameError.value = ''
  savingUsername.value = true
  try {
    auth.user = (await client.patch('/users/me/username', { username: username.value })).data
    toast.success('Логин изменён. Следующая смена — через 6 месяцев')
  } catch (err) {
    const status = err?.response?.status
    usernameError.value =
      status === 409 ? 'Этот логин уже занят' : status === 422 ? '3–50 символов: латинские буквы, цифры, . _ -' : errorMessage(err)
  } finally {
    savingUsername.value = false
  }
}

async function onAvatar(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  uploading.value = true
  const form = new FormData()
  form.append('file', file)
  try {
    auth.user = (await client.put('/users/me/avatar', form)).data
    toast.success('Аватар обновлён')
  } catch (err) {
    toast.error(errorMessage(err, 'Не удалось загрузить аватар'))
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="profile">
    <div v-if="!user.is_email_verified" class="banner" role="status">
      Email не подтверждён — некоторые функции недоступны.
    </div>
    <section class="block avatar-block">
      <UserAvatar :user="user" :size="88" />
      <div>
        <BaseButton variant="secondary" size="sm" :loading="uploading" @click="fileInput.click()">Загрузить аватар</BaseButton>
        <p class="muted">JPEG, PNG или WebP до 2 МБ</p>
        <input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp" class="hidden" tabindex="-1"
          aria-hidden="true" @change="onAvatar" />
      </div>
    </section>
    <dl class="facts">
      <dt>Роль</dt>
      <dd>{{ ROLE_LABELS[user.role] }}</dd>
      <dt>Email</dt>
      <dd>{{ user.email }} <span class="tag" :class="{ 'tag--ok': user.is_email_verified }">{{ user.is_email_verified ? 'подтверждён' : 'не подтверждён' }}</span></dd>
    </dl>
    <form class="block form" @submit.prevent="saveName">
      <BaseInput v-model="displayName" label="Отображаемое имя" maxlength="50" hint="Видно в шапке вместо логина" />
      <BaseButton type="submit" :loading="savingName">Сохранить имя</BaseButton>
    </form>
    <form class="block form" @submit.prevent="saveUsername">
      <BaseInput v-model="username" label="Логин" :disabled="usernameLocked" :error="usernameError"
        :hint="usernameLocked ? `Следующая смена — ${nextChange.toLocaleDateString('ru-RU')}` : 'Менять можно раз в 6 месяцев'" />
      <BaseButton type="submit" variant="secondary" :loading="savingUsername" :disabled="usernameLocked || username === user.username">
        Сменить логин
      </BaseButton>
    </form>
  </div>
</template>

<style scoped>
.profile {
  display: grid;
  gap: 20px;
}
.banner {
  padding: 12px 14px;
  border-radius: var(--radius-sm);
  background: #fff7e6;
  color: #92400e;
}
.avatar-block {
  display: flex;
  align-items: center;
  gap: 18px;
}
.form {
  display: grid;
  gap: 12px;
  max-width: 420px;
  justify-items: start;
}
.facts {
  display: grid;
  grid-template-columns: 90px 1fr;
  gap: 8px 12px;
  margin: 0;
}
.facts dt {
  color: var(--color-muted);
}
.facts dd {
  margin: 0;
}
.tag {
  margin-left: 6px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #fff7e6;
  color: #92400e;
  font-size: 12px;
}
.tag--ok {
  background: #ecfdf3;
  color: var(--color-success);
}
.muted {
  margin: 6px 0 0;
  color: var(--color-muted);
  font-size: 13px;
}
.hidden {
  display: none;
}
</style>
