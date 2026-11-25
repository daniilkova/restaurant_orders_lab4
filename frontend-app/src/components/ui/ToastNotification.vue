<script setup>
const props = defineProps({
  type: { type: String, default: 'info', validator: (v) => ['success', 'error', 'info'].includes(v) },
  message: { type: String, required: true },
})
const emit = defineEmits(['close'])
const ICONS = { success: '✓', error: '!', info: 'i' }
</script>

<template>
  <div
    class="toast"
    :class="`toast--${props.type}`"
    :role="props.type === 'error' ? 'alert' : 'status'"
    :aria-live="props.type === 'error' ? 'assertive' : 'polite'"
  >
    <span class="toast__icon" aria-hidden="true">{{ ICONS[props.type] }}</span>
    <span class="toast__message">{{ props.message }}</span>
    <button type="button" class="toast__close" aria-label="Закрыть уведомление" @click="emit('close')">×</button>
  </div>
</template>

<style scoped>
.toast {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 260px;
  max-width: 380px;
  padding: 12px 14px;
  border-radius: var(--radius-md, 10px);
  background: var(--color-surface, #fff);
  border-left: 4px solid var(--color-info, #1d4ed8);
  box-shadow: var(--shadow-lg, 0 10px 30px rgba(0, 0, 0, 0.18));
}
.toast--success { border-left-color: var(--color-success, #15803d); }
.toast--error { border-left-color: var(--color-danger, #b91c1c); }
.toast__icon {
  display: grid;
  place-items: center;
  flex: none;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  background: var(--color-info, #1d4ed8);
}
.toast--success .toast__icon { background: var(--color-success, #15803d); }
.toast--error .toast__icon { background: var(--color-danger, #b91c1c); }
.toast__message {
  flex: 1;
  font-size: 15px;
}
.toast__close {
  border: none;
  background: transparent;
  font-size: 20px;
  line-height: 1;
  color: var(--color-muted, #7a6a5b);
  cursor: pointer;
}
.toast__close:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring, 0 0 0 3px rgba(194, 65, 12, 0.35));
  border-radius: 4px;
}
</style>
