// Форма: значения, клиентская валидация, отправка и раскладка ошибок 422 по полям.
import { computed, reactive, ref, toRaw, watch } from 'vue'
import { errorMessage, parseValidationError } from '@/api/errors'

// глубокая копия обычных данных (props родителя — readonly-прокси, structuredClone их не принимает)
const clone = (value) => JSON.parse(JSON.stringify(toRaw(value)))

export function useForm(initialValues, validators = {}, onSubmit) {
  const initial = clone(initialValues)
  // форма работает с копией и не меняет объект родителя (например, загруженную запись)
  const values = reactive(clone(initialValues))
  const errors = reactive({})
  const submitError = ref('')
  const isSubmitting = ref(false)

  const fields = Object.keys(initial)
  const isValid = computed(() => Object.values(errors).every((e) => !e))
  const isDirty = computed(() => fields.some((f) => values[f] !== initial[f]))

  function validateField(field) {
    const rule = validators[field]
    errors[field] = rule ? rule(values[field], values) || '' : ''
    return !errors[field]
  }

  // Ошибка поля перепроверяется сразу при вводе, а не только при потере фокуса: иначе
  // подсказка исчезала бы при blur, форма «прыгала», и клик по кнопке «Сохранить» терялся
  for (const field of fields) {
    watch(
      () => values[field],
      () => {
        if (errors[field]) validateField(field)
      },
    )
  }

  function validate() {
    return fields.map(validateField).every(Boolean)
  }

  async function submit() {
    if (isSubmitting.value) return false // повторное нажатие во время запроса
    submitError.value = ''
    if (!validate()) return false
    isSubmitting.value = true
    try {
      await onSubmit({ ...values })
      return true
    } catch (err) {
      const { fieldErrors, general } = parseValidationError(err, fields)
      Object.assign(errors, fieldErrors)
      submitError.value = general || (Object.keys(fieldErrors).length ? '' : errorMessage(err))
      return false
    } finally {
      isSubmitting.value = false
    }
  }

  function reset() {
    Object.assign(values, clone(initial))
    for (const key of Object.keys(errors)) errors[key] = ''
    submitError.value = ''
  }

  return { values, errors, submitError, isSubmitting, isValid, isDirty, validateField, validate, submit, reset }
}
