<template>
  <section class="not-found">
    <p class="not-found__code">404</p>
    <h1>Страница не найдена</h1>
    <RouterLink to="/">На главную</RouterLink>
  </section>
</template>

<style scoped>
.not-found {
  text-align: center;
  margin-top: 60px;
}
.not-found__code {
  margin: 0;
  font-size: 64px;
  font-weight: 800;
  color: var(--color-primary);
}
</style>
