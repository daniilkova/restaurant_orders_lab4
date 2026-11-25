<script setup>
import { RouterLink, RouterView, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

function logout() {
  auth.logout()
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
          <RouterLink to="/" class="nav__link">Главная</RouterLink>
          <span v-if="auth.user" class="nav__user">
            {{ auth.user.username }}
            <span v-if="auth.isAdmin" class="nav__role">персонал</span>
          </span>
          <button type="button" class="nav__logout" @click="logout">Выйти</button>
        </template>
        <RouterLink v-else to="/login" class="nav__link">Войти</RouterLink>
      </nav>
    </div>
  </header>
  <main class="main">
    <RouterView />
  </main>
</template>

<style scoped>
.header {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}
.header__inner {
  max-width: 1040px;
  margin: 0 auto;
  padding: 14px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  font-size: 18px;
  color: var(--color-text);
  text-decoration: none;
}
.brand__logo {
  font-size: 22px;
}
.nav {
  display: flex;
  align-items: center;
  gap: 16px;
}
.nav__link {
  color: var(--color-text);
  text-decoration: none;
  font-weight: 500;
}
.nav__link.router-link-exact-active {
  color: var(--color-primary);
}
.nav__user {
  color: var(--color-muted);
  font-size: 14px;
}
.nav__role {
  margin-left: 6px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 600;
}
.nav__logout {
  border: 1px solid var(--color-border);
  background: transparent;
  border-radius: 8px;
  padding: 6px 14px;
  cursor: pointer;
}
.nav__logout:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.main {
  max-width: 1040px;
  margin: 0 auto;
  padding: 28px 20px 48px;
}
</style>
