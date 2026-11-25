<script setup>
import { RouterLink, RouterView, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ToastContainer from '@/components/ui/ToastContainer.vue'
import UserAvatar from '@/components/UserAvatar.vue'

const auth = useAuthStore()
const router = useRouter()

async function logout() {
  await auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <header class="header">
    <div class="header__inner">
      <RouterLink to="/" class="brand">
        <span class="brand__logo" aria-hidden="true">🍽</span>
        <span>Ресторан «Пряность»</span>
      </RouterLink>
      <nav class="nav" aria-label="Основная навигация">
        <template v-if="auth.isAuthenticated">
          <RouterLink to="/" class="nav__link">Меню</RouterLink>
          <RouterLink to="/orders" class="nav__link">{{ auth.isStaff ? 'Все заказы' : 'Мои заказы' }}</RouterLink>
          <RouterLink to="/account" class="nav__user" :aria-label="`Аккаунт: ${auth.displayName}`">
            <UserAvatar :user="auth.user" :size="30" />
            <span class="nav__name">{{ auth.displayName }}</span>
            <span v-if="auth.isStaff" class="nav__role">{{ auth.isAdmin ? 'админ' : 'модератор' }}</span>
          </RouterLink>
          <button type="button" class="nav__logout" @click="logout">Выйти</button>
        </template>
        <template v-else>
          <RouterLink to="/login" class="nav__link">Войти</RouterLink>
          <RouterLink to="/register" class="nav__link nav__link--accent">Регистрация</RouterLink>
        </template>
      </nav>
    </div>
  </header>
  <main class="main">
    <RouterView />
  </main>
  <ToastContainer />
</template>

<style scoped>
.header { background: var(--color-surface); border-bottom: 1px solid var(--color-border); }
.header__inner { max-width: 1040px; margin: 0 auto; padding: 12px 20px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.brand { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 18px; color: var(--color-text); text-decoration: none; }
.brand__logo { font-size: 22px; }
.nav { display: flex; align-items: center; gap: 16px; }
.nav__link { color: var(--color-text); text-decoration: none; font-weight: 500; }
.nav__link.router-link-exact-active { color: var(--color-primary); }
.nav__link--accent { color: var(--color-primary); }
.nav__user { display: flex; align-items: center; gap: 8px; color: var(--color-text); text-decoration: none; font-size: 14px; }
.nav__user.router-link-active .nav__name { color: var(--color-primary); }
.nav__role { padding: 2px 8px; border-radius: 999px; background: var(--color-primary-soft); color: var(--color-primary); font-size: 12px; font-weight: 600; }
.nav__logout { border: 1px solid var(--color-border); background: transparent; border-radius: 8px; padding: 6px 14px; cursor: pointer; }
.nav__logout:hover { border-color: var(--color-primary); color: var(--color-primary); }
.main { max-width: 1040px; margin: 0 auto; padding: 28px 20px 48px; }
</style>
