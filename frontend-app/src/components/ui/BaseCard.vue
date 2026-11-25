<script setup>
defineProps({
  as: { type: String, default: 'div' },          // div | li | article — корректная разметка в списках
  interactive: { type: Boolean, default: false },
})
</script>

<template>
  <component :is="as" class="card" :class="{ 'card--interactive': interactive }">
    <header v-if="$slots.header" class="card__header"><slot name="header" /></header>
    <div class="card__body"><slot /></div>
    <footer v-if="$slots.footer" class="card__footer"><slot name="footer" /></footer>
  </component>
</template>

<style scoped>
.card {
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border, #e8dfd3);
  border-radius: var(--radius-md, 10px);
  box-shadow: var(--shadow-sm, 0 1px 3px rgba(0, 0, 0, 0.08));
  transition: transform 0.15s, box-shadow 0.15s;
}
.card--interactive:hover,
.card--interactive:focus-within {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg, 0 10px 30px rgba(0, 0, 0, 0.15));
}
.card__body {
  flex: 1;
  padding: 16px;
}
.card__footer {
  padding: 12px 16px;
  border-top: 1px solid var(--color-border, #e8dfd3);
}
</style>
