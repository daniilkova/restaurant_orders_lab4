<script setup>
// Одна форма для создания и редактирования блюда. Отправку выполняет родитель через
// prop onSubmit (async-функция): форма дожидается ответа и раскладывает ошибки 422 по полям.
// emit('submit') для этого не подходит — emit не возвращает промис.
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { useForm } from '@/composables/useForm'

const props = defineProps({
  initialValues: {
    type: Object,
    default: () => ({ name: '', description: '', price: null, is_available: true, min_age: 0 }),
  },
  submitLabel: { type: String, default: 'Сохранить' },
  onSubmit: { type: Function, required: true },
})
const emit = defineEmits(['cancel'])

const validators = {
  name: (v) => (!v?.trim() ? 'Введите название' : v.trim().length > 100 ? 'Не больше 100 символов' : ''),
  description: (v) => (v && v.length > 500 ? 'Не больше 500 символов' : ''),
  // верхнюю границу (100 000 ₽) проверяет сервер — так видна обработка его ошибки 422
  price: (v) => (v === null || v === '' || Number.isNaN(v) ? 'Укажите цену' : v <= 0 ? 'Цена должна быть больше 0' : ''),
}

const initial = {
  name: props.initialValues.name ?? '',
  description: props.initialValues.description ?? '',
  price: props.initialValues.price ?? null,
  is_available: props.initialValues.is_available ?? true,
  min_age: props.initialValues.min_age ?? 0,
}
const form = useForm(initial, validators, (values) => props.onSubmit(values))
</script>

<template>
  <form class="form" novalidate @submit.prevent="form.submit">
    <BaseInput
      v-model="form.values.name"
      label="Название"
      required
      maxlength="100"
      :error="form.errors.name"
      @blur="form.validateField('name')"
    />
    <BaseInput
      v-model="form.values.description"
      label="Описание"
      multiline
      hint="Состав, вес или объём порции"
      :error="form.errors.description"
    />
    <BaseInput
      v-model.number="form.values.price"
      label="Цена, ₽"
      type="number"
      min="1"
      step="1"
      inputmode="decimal"
      required
      :error="form.errors.price"
      @blur="form.validateField('price')"
    />
    <label class="check">
      <input v-model="form.values.is_available" type="checkbox" />
      <span>В продаже</span>
    </label>
    <label class="check">
      <input
        type="checkbox"
        :checked="form.values.min_age >= 18"
        @change="form.values.min_age = $event.target.checked ? 18 : 0"
      />
      <span>Только 18+ (алкоголь) — видно после возрастной верификации</span>
    </label>
    <p v-if="form.submitError.value" class="form__error" role="alert">{{ form.submitError.value }}</p>
    <div class="form__actions">
      <BaseButton variant="secondary" :disabled="form.isSubmitting.value" @click="emit('cancel')">Отмена</BaseButton>
      <BaseButton type="submit" :loading="form.isSubmitting.value">{{ submitLabel }}</BaseButton>
    </div>
  </form>
</template>

<style scoped>
.form {
  display: grid;
  gap: 18px;
}
.check {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 500;
}
.check input {
  width: 18px;
  height: 18px;
  accent-color: var(--color-primary);
}
.form__error {
  margin: 0;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: var(--color-danger-soft);
  color: var(--color-danger);
}
.form__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
