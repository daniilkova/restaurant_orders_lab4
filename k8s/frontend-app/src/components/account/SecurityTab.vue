<script setup>
// Безопасность — список независимых карточек: у каждой своё состояние, ошибки и запросы,
// их проще тестировать и развивать, чем одну длинную форму
import ChangePasswordCard from './ChangePasswordCard.vue'
import TwoFactorCard from './TwoFactorCard.vue'
import SessionsCard from './SessionsCard.vue'
import AgeVerificationCard from './AgeVerificationCard.vue'
</script>

<template>
  <div class="cards">
    <TwoFactorCard />
    <ChangePasswordCard />
    <SessionsCard />
    <AgeVerificationCard />
  </div>
</template>

<style scoped>
.cards {
  display: grid;
  gap: 16px;
}
.cards :deep(.card__body) {
  padding: 20px;
}
</style>
