<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import UserAvatar from '@/components/UserAvatar.vue'
import ProfileTab from '@/components/account/ProfileTab.vue'
import SettingsTab from '@/components/account/SettingsTab.vue'
import SecurityTab from '@/components/account/SecurityTab.vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'

const auth = useAuthStore()
const route = useRoute()
const toast = useToast()
const TABS = [
  { id: 'profile', label: 'Профиль', component: ProfileTab },
  { id: 'settings', label: 'Настройки', component: SettingsTab },
  { id: 'security', label: 'Безопасность', component: SecurityTab },
]
const active = ref(TABS.some((t) => t.id === route.query.tab) ? route.query.tab : 'profile')

onMounted(() => {
  if (route.query.age === 'success') toast.success('Возраст подтверждён')
  if (route.query.age === 'failure') toast.error('Не удалось подтвердить возраст')
})
</script>

<template>
  <section v-if="auth.user" class="account">
    <header class="account__head">
      <UserAvatar :user="auth.user" :size="64" />
      <div>
        <h1 class="account__name">{{ auth.displayName }}</h1>
        <p class="account__login">@{{ auth.user.username }}</p>
      </div>
    </header>
    <div class="tabs" role="tablist" aria-label="Разделы аккаунта">
      <button
        v-for="tab in TABS"
        :id="`tab-${tab.id}`"
        :key="tab.id"
        type="button"
        role="tab"
        class="tabs__tab"
        :aria-selected="active === tab.id"
        :aria-controls="`panel-${tab.id}`"
        @click="active = tab.id"
      >
        {{ tab.label }}
      </button>
    </div>
    <div
      v-for="tab in TABS"
      v-show="active === tab.id"
      :id="`panel-${tab.id}`"
      :key="tab.id"
      role="tabpanel"
      :aria-labelledby="`tab-${tab.id}`"
      class="account__panel"
    >
      <component :is="tab.component" v-if="active === tab.id" />
    </div>
  </section>
</template>

<style scoped>
.account__head { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
.account__name { margin: 0; font-size: 26px; }
.account__login { margin: 2px 0 0; color: var(--color-muted); }
.tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--color-border); margin-bottom: 20px; overflow-x: auto; }
.tabs__tab { padding: 10px 16px; border: none; border-bottom: 3px solid transparent; background: none; font-weight: 600; color: var(--color-muted); cursor: pointer; }
.tabs__tab[aria-selected='true'] { color: var(--color-primary); border-bottom-color: var(--color-primary); }
.tabs__tab:focus-visible { outline: none; box-shadow: var(--focus-ring); border-radius: 6px 6px 0 0; }
.account__panel { padding: 4px 0; }
</style>
