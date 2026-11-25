<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import client from '@/api/client'
import { errorMessage } from '@/api/errors'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'

const auth = useAuthStore()
const router = useRouter()
const toast = useToast()
const sessions = ref([])
const loading = ref(true)
const error = ref('')

function device(ua) {
  if (!ua) return 'Неизвестное устройство'
  const os = /Windows/.test(ua) ? 'Windows' : /Android/.test(ua) ? 'Android' : /iPhone|iPad/.test(ua) ? 'iOS' : /Mac OS/.test(ua) ? 'macOS' : /Linux/.test(ua) ? 'Linux' : ''
  const browser = /Edg\//.test(ua) ? 'Edge' : /Chrome\//.test(ua) ? 'Chrome' : /Firefox\//.test(ua) ? 'Firefox' : /Safari\//.test(ua) ? 'Safari' : ua.split(' ')[0]
  return [browser, os].filter(Boolean).join(', ')
}
const fmt = (iso) => new Date(iso).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

async function load() {
  loading.value = true
  try {
    sessions.value = (await client.get('/auth/sessions')).data
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

async function revoke(session) {
  try {
    await client.delete(`/auth/sessions/${session.id}`)
    if (session.current) {
      auth.clear()
      toast.info('Сессия завершена')
      router.push({ name: 'login' })
      return
    }
    sessions.value = sessions.value.filter((s) => s.id !== session.id)
    toast.success('Сессия на другом устройстве завершена')
  } catch (err) {
    toast.error(errorMessage(err))
  }
}

async function revokeOthers() {
  await client.post('/auth/sessions/revoke-others')
  sessions.value = sessions.value.filter((s) => s.current)
  toast.success('Все остальные сессии завершены')
}

onMounted(load)
</script>

<template>
  <BaseCard as="article" class="sec-card">
    <div class="head">
      <h3>Активные сессии</h3>
      <BaseButton v-if="sessions.length > 1" variant="ghost" size="sm" @click="revokeOthers">Завершить остальные</BaseButton>
    </div>
    <p v-if="loading" aria-live="polite">Загрузка…</p>
    <p v-else-if="error" class="error" role="alert">{{ error }}</p>
    <ul v-else class="list">
      <li v-for="s in sessions" :key="s.id" class="item">
        <div>
          <p class="item__device">{{ device(s.user_agent) }} <span v-if="s.current" class="current">это устройство</span></p>
          <p class="item__meta">IP {{ s.ip }} · вход {{ fmt(s.created_at) }} · активность {{ fmt(s.last_used_at) }}</p>
        </div>
        <BaseButton variant="secondary" size="sm" @click="revoke(s)">{{ s.current ? 'Выйти' : 'Завершить' }}</BaseButton>
      </li>
    </ul>
  </BaseCard>
</template>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: center; }
h3 { margin: 0 0 10px; }
.list { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.item { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 10px 12px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); }
.item__device { margin: 0; font-weight: 600; }
.item__meta { margin: 2px 0 0; color: var(--color-muted); font-size: 13px; }
.current { margin-left: 6px; padding: 1px 8px; border-radius: 999px; background: #ecfdf3; color: var(--color-success); font-size: 12px; font-weight: 600; }
.error { color: var(--color-danger); }
</style>
