<script setup>
import { computed } from 'vue'
import client from '@/api/client'

const props = defineProps({
  user: { type: Object, required: true },
  size: { type: Number, default: 32 },
})
const src = computed(() =>
  props.user.avatar_url ? `${client.defaults.baseURL?.replace(/\/$/, '') ?? ''}${props.user.avatar_url}` : null,
)
const initials = computed(() => (props.user.display_name || props.user.username || '?').slice(0, 1).toUpperCase())
</script>

<template>
  <span class="avatar" :style="{ width: `${size}px`, height: `${size}px`, fontSize: `${size * 0.45}px` }">
    <img v-if="src" :src="src" alt="" />
    <span v-else aria-hidden="true">{{ initials }}</span>
  </span>
</template>

<style scoped>
.avatar {
  display: inline-grid;
  place-items: center;
  flex: none;
  overflow: hidden;
  border-radius: 50%;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-weight: 700;
}
.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
