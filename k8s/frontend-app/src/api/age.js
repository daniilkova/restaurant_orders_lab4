import client from './client'

export const REGISTRATION_TOKEN_KEY = 'registration_token'

/** Запросить у бэкенда сессию Self и перейти на страницу верификации. */
export async function startAgeVerification(registrationToken) {
  const headers = registrationToken ? { 'X-Registration-Token': registrationToken } : {}
  const { data } = await client.post('/auth/age-session', null, { headers })
  window.location.assign(data.verificationUrl)
}

export async function completeRegistration(registrationToken) {
  const { data } = await client.post('/auth/complete-registration', { registration_token: registrationToken })
  return data
}
