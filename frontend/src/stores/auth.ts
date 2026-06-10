import { computed, reactive } from 'vue'
import { getCurrentUser, login as loginApi, register as registerApi } from '@/api'
import type { AuthResponse, LoginRequest, RegisterRequest, User } from '@/types'

const AUTH_TOKEN_KEY = 'ai_change_map_token'

const state = reactive({
  token: localStorage.getItem(AUTH_TOKEN_KEY) || '',
  user: null as User | null,
  initialized: false
})

function applyAuth(response: AuthResponse) {
  state.token = response.access_token
  state.user = response.user
  localStorage.setItem(AUTH_TOKEN_KEY, response.access_token)
}

async function initAuth() {
  if (state.initialized) return

  if (!state.token) {
    state.initialized = true
    return
  }

  try {
    state.user = await getCurrentUser()
  } catch {
    logout(false)
  } finally {
    state.initialized = true
  }
}

async function login(payload: LoginRequest) {
  const response = await loginApi(payload)
  applyAuth(response)
}

async function register(payload: RegisterRequest) {
  const response = await registerApi(payload)
  applyAuth(response)
}

function logout(resetInitialized = true) {
  state.token = ''
  state.user = null
  localStorage.removeItem(AUTH_TOKEN_KEY)
  if (resetInitialized) {
    state.initialized = true
  }
}

export function useAuth() {
  return {
    state,
    isAuthenticated: computed(() => Boolean(state.token && state.user)),
    initAuth,
    login,
    register,
    logout
  }
}
