<script setup>
// Заготовка для будущих настроек: выбор сохраняется в браузере (это не персональные данные)
import { ref, watch } from 'vue'

function load(key, fallback) {
  try {
    return localStorage.getItem(key) ?? fallback
  } catch {
    return fallback
  }
}
const theme = ref(load('pref_theme', 'light'))
const language = ref(load('pref_lang', 'ru'))
watch(theme, (v) => localStorage.setItem('pref_theme', v))
watch(language, (v) => localStorage.setItem('pref_lang', v))
</script>

<template>
  <div class="settings">
    <fieldset class="group">
      <legend>Тема оформления</legend>
      <label><input v-model="theme" type="radio" value="light" /> Светлая</label>
      <label><input v-model="theme" type="radio" value="dark" disabled /> Тёмная <span class="soon">скоро</span></label>
    </fieldset>
    <fieldset class="group">
      <legend>Язык интерфейса</legend>
      <label><input v-model="language" type="radio" value="ru" /> Русский</label>
      <label><input v-model="language" type="radio" value="en" disabled /> English <span class="soon">скоро</span></label>
    </fieldset>
  </div>
</template>

<style scoped>
.settings {
  display: grid;
  gap: 18px;
}
.group {
  display: grid;
  gap: 8px;
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}
legend {
  padding: 0 6px;
  font-weight: 600;
}
.soon {
  margin-left: 6px;
  padding: 1px 8px;
  border-radius: 999px;
  background: var(--color-secondary);
  color: var(--color-muted);
  font-size: 12px;
}
</style>
