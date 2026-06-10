// API 调用封装
import axios from 'axios'
import type {
  EditResponse,
  ProvidersListResponse,
  SessionListResponse,
  Session,
  EditMetadata,
  TaskMode,
  AuthResponse,
  LoginRequest,
  RegisterRequest,
  User
} from '@/types'

const AUTH_TOKEN_KEY = 'ai_change_map_token'

const api = axios.create({
  baseURL: '/',
  timeout: 300000 // 5分钟，需大于后端 provider 的 240s 超时
})

// 请求拦截器
api.interceptors.request.use(
  config => {
    const token = localStorage.getItem(AUTH_TOKEN_KEY)
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  response => response.data,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem(AUTH_TOKEN_KEY)
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    const message = error.response?.data?.detail || error.message || '请求失败'
    return Promise.reject(new Error(message))
  }
)

/**
 * 用户注册
 */
export async function register(payload: RegisterRequest): Promise<AuthResponse> {
  return api.post('/api/auth/register', payload)
}

/**
 * 用户登录
 */
export async function login(payload: LoginRequest): Promise<AuthResponse> {
  return api.post('/api/auth/login', payload)
}

/**
 * 获取当前用户
 */
export async function getCurrentUser(): Promise<User> {
  return api.get('/api/auth/me')
}

/**
 * 图像编辑接口
 */
export async function editImage(
  mainImage: File,
  instruction: string,
  options: {
    sessionId?: string
    parentId?: number
    parentResultIndex?: number
    taskMode?: TaskMode
    maskImage?: File
    editMetadata?: EditMetadata
    provider?: string
    outputCount?: number
    referenceImages?: File[]
  } = {}
): Promise<EditResponse> {
  const formData = new FormData()
  formData.append('main_image', mainImage)
  formData.append('instruction', instruction)

  if (options.sessionId) {
    formData.append('session_id', options.sessionId)
  }
  if (options.parentId) {
    formData.append('parent_id', String(options.parentId))
  }
  if (options.parentResultIndex !== undefined) {
    formData.append('parent_result_index', String(options.parentResultIndex))
  }
  if (options.taskMode) {
    formData.append('task_mode', options.taskMode)
  }
  if (options.maskImage) {
    formData.append('mask_image', options.maskImage)
  }
  if (options.editMetadata) {
    formData.append('edit_metadata', JSON.stringify(options.editMetadata))
  }
  if (options.provider) {
    formData.append('provider', options.provider)
  }
  if (options.outputCount) {
    formData.append('output_count', String(options.outputCount))
  }
  if (options.referenceImages) {
    options.referenceImages.forEach(img => {
      formData.append('reference_images', img)
    })
  }

  return api.post('/api/edit', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

/**
 * 获取可用 providers 列表
 */
export async function getProviders(): Promise<ProvidersListResponse> {
  return api.get('/api/providers')
}

/**
 * 获取会话列表
 */
export async function getSessions(page: number = 1, pageSize: number = 20): Promise<SessionListResponse> {
  return api.get('/api/history', {
    params: { page, page_size: pageSize }
  })
}

/**
 * 获取单个会话详情
 */
export async function getSession(sessionId: string): Promise<Session> {
  return api.get(`/api/history/${sessionId}`)
}

/**
 * 删除会话
 */
export async function deleteSession(sessionId: string): Promise<void> {
  return api.delete(`/api/history/${sessionId}`)
}

export default api
