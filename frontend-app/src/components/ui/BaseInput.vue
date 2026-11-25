<script setup>
// Поле ввода с подписью, подсказкой и ошибкой. Ошибка связана с полем через aria-describedby.
import { computed, useId } from 'vue'

defineOptions({ inheritAttrs: false })

// v-model и v-model.number: модификаторы приходят вторым элементом defineModel
const [model, modifiers] = defineModel({ type: [String, Number, null], default: '' })
const props = defineProps({
  label: { type: String, required: true },
  id: { type: String, default: '' },
  type: { type: String, default: 'text' },
  hint: { type: String, default: '' },
  error: { type: String, default: '' },
  multiline: { type: Boolean, default: false },
  required: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  number: { type: Boolean, default: false },
})
const emit = defineEmits(['blur'])

const autoId = useId()
const inputId = computed(() => props.id || `field-${autoId}`)
const hintId = computed(() => `${inputId.value}-hint`)
const errorId = computed(() => `${inputId.value}-error`)
const describedBy = computed(() =>
  [props.error ? errorId.value : null, props.hint ? hintId.value : null].filter(Boolean).join(' ') || undefined,
)

function onInput(event) {
  const raw = event.target.value
  if (props.number || modifiers.number) {
    model.value = raw === '' ? null : Number(raw)
  } else {
    model.value = raw
  }
}
</script>

<template>
  <div class="field" :class="{ 'field--error': error, 'field--disabled': disabled }">
    <label class="field__label" :for="inputId">
      {{ label }}<span v-if="required" class="field__required" aria-hidden="true"> *</span>
    </label>
    <component
      :is="multiline ? 'textarea' : 'input'"
      v-bind="$attrs"
      :id="inputId"
      class="field__control"
      :type="multiline ? undefined : type"
      :value="model ?? ''"
      :required="required"
      :disabled="disabled"
      :aria-invalid="error ? 'true' : undefined"
      :aria-describedby="describedBy"
      :rows="multiline ? 4 : undefined"
      @input="onInput"
      @blur="emit('blur')"
    />
    <p v-if="hint && !error" :id="hintId" class="field__hint">{{ hint }}</p>
    <p v-if="error" :id="errorId" class="field__error" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
.field {
  display: grid;
  gap: 6px;
}
.field__label {
  font-size: 14px;
  font-weight: 600;
}
.field__required {
  color: var(--color-danger, #b91c1c);
}
.field__control {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--color-border, #e8dfd3);
  border-radius: var(--radius-sm, 6px);
  background: #fff;
  color: inherit;
  font: inherit;
  transition: border-color 0.15s, box-shadow 0.15s;
}
textarea.field__control {
  resize: vertical;
  min-height: 90px;
}
.field__control:hover:not(:disabled) {
  border-color: #d6c8b6;
}
.field__control:focus-visible {
  outline: none;
  border-color: var(--color-primary, #c2410c);
  box-shadow: var(--focus-ring, 0 0 0 3px rgba(194, 65, 12, 0.35));
}
.field__control:disabled {
  background: var(--color-secondary, #f3ede5);
  cursor: not-allowed;
}
.field--error .field__control {
  border-color: var(--color-danger, #b91c1c);
}
.field__hint {
  margin: 0;
  font-size: 13px;
  color: var(--color-muted, #7a6a5b);
}
.field__error {
  margin: 0;
  font-size: 13px;
  color: var(--color-danger, #b91c1c);
}
</style>
