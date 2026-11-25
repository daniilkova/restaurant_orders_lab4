<script setup>
// Кнопка дизайн-системы. Атрибуты родителя (aria-*, data-*, @click) уходят на <button>.
defineOptions({ inheritAttrs: false })

const props = defineProps({
  variant: { type: String, default: 'primary', validator: (v) => ['primary', 'secondary', 'danger', 'ghost'].includes(v) },
  size: { type: String, default: 'md', validator: (v) => ['sm', 'md', 'lg'].includes(v) },
  type: { type: String, default: 'button' },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  block: { type: Boolean, default: false },
})
</script>

<template>
  <button
    v-bind="$attrs"
    :type="props.type"
    class="btn"
    :class="[`btn--${variant}`, `btn--${size}`, { 'btn--block': block, 'btn--loading': loading }]"
    :disabled="disabled || loading"
    :aria-busy="loading || undefined"
  >
    <span v-if="loading" class="btn__spinner" aria-hidden="true" />
    <span class="btn__label"><slot /></span>
  </button>
</template>

<style scoped>
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm, 6px);
  font-weight: 600;
  line-height: 1.2;
  cursor: pointer;
  transition: background-color 0.15s, border-color 0.15s, color 0.15s, box-shadow 0.15s;
}
.btn:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring, 0 0 0 3px rgba(194, 65, 12, 0.35));
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.btn--loading {
  cursor: progress;
}
.btn--sm { padding: 6px 12px; font-size: 14px; }
.btn--md { padding: 10px 18px; font-size: 15px; }
.btn--lg { padding: 13px 24px; font-size: 17px; }
.btn--block { width: 100%; }
.btn--primary {
  background: var(--color-primary, #c2410c);
  color: #fff;
}
.btn--primary:hover:not(:disabled) { background: var(--color-primary-hover, #9a3412); }
.btn--secondary {
  background: var(--color-secondary, #f3ede5);
  color: var(--color-text, #2b2118);
  border-color: var(--color-border, #e8dfd3);
}
.btn--secondary:hover:not(:disabled) { background: var(--color-secondary-hover, #e9e0d4); }
.btn--danger {
  background: var(--color-danger, #b91c1c);
  color: #fff;
}
.btn--danger:hover:not(:disabled) { background: #991b1b; }
.btn--ghost {
  background: transparent;
  color: var(--color-primary, #c2410c);
}
.btn--ghost:hover:not(:disabled) { background: var(--color-primary-soft, #fff1e6); }
.btn__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
