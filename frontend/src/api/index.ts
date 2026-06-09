// API 调用封装
import axios from 'axios'
import type {
  EditResponse,
  ProvidersListResponse,
  SessionListResponse,
  Session
} from '@/types'

const api = axios.create({
  baseURL: '/',
  timeout: 300000 // 5分钟，需大于后端 provider 的 240s 超时
})

// 请求拦截器
api.interceptors.request.use(
  config => {
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
    const message = error.response?.data?.detail || error.message || '请求失败'
    return Promise.reject(new Error(message))
  }
)

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
