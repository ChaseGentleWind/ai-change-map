// TypeScript 类型定义

export interface User {
  id: number
  username: string
  phone?: string
  is_active: boolean
  is_admin: boolean
  created_at: string
}

export interface LoginRequest {
  username_or_phone: string
  password: string
}

export interface RegisterRequest {
  username: string
  phone: string
  password: string
}

export interface UpdateProfileRequest {
  username: string
  phone: string
}

export interface UpdatePasswordRequest {
  current_password: string
  new_password: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

export interface EditRequest {
  instruction: string
  session_id?: string
  parent_id?: number
  parent_result_index?: number
  task_mode?: TaskMode
  output_count?: number
    provider?: string
    output_resolution?: string
}

export type TaskMode = 'general' | 'local_edit' | 'text_layer'

export interface TextLayer {
  id: string
  text: string
  x: number
  y: number
  fontSize: number
  color: string
}

export interface EditMetadata {
  task_mode: TaskMode
  text_layers?: TextLayer[]
  model_selection?: {
    provider: string
    model: string
    resolution?: string
    price_per_image?: number
  }
  mask?: {
    brushSize: number
    feather: number
  }
}

export interface EditResponse {
  record_id: number
  session_id: string
  provider: string
  model: string
  task_type: string
  fallback_used?: string
  results: string[]
  usage: {
    input_tokens: number
    output_tokens: number
    total_tokens: number
  }
  cost?: number
  cost_currency?: string
  duration_ms: number
}

export interface EditRecord {
  id: number
  session_id: string
  parent_id?: number
  main_image_url: string
  reference_urls?: string[]
  mask_url?: string
  edit_metadata?: EditMetadata
  instruction: string
  task_type?: string
  provider: string
  model: string
  fallback_used?: string
  result_urls?: string[]
  status: string
  error_message?: string
  cost?: number
  cost_currency?: string
  duration_ms?: number
  created_at: string
}

export interface Session {
  id: string
  title?: string
  original_url: string
  records: EditRecord[]
  created_at: string
  updated_at: string
}

export interface SessionListItem {
  id: string
  title?: string
  original_url: string
  last_result_url?: string
  record_count: number
  created_at: string
  updated_at: string
}

export interface SessionListResponse {
  total: number
  page: number
  page_size: number
  items: SessionListItem[]
}

export interface UsageSummary {
  period: 'today' | 'all'
  currency: 'CNY'
  cost: number
  image_count: number
  models: Array<{
    model: string
    image_count: number
    unit_price: number
    cost: number
  }>
}

export interface AdminUserListItem {
  id: number
  username: string
  phone?: string
  is_active: boolean
  is_admin: boolean
  session_count: number
  record_count: number
  last_active_at?: string
  created_at: string
}

export interface AdminUserDetail extends AdminUserListItem {}

export interface AdminUserListResponse {
  total: number
  page: number
  page_size: number
  items: AdminUserListItem[]
}

export interface AdminUpdateUserRequest {
  username: string
  phone: string
  is_active: boolean
}

export interface AdminUserHistoryResponse {
  user: AdminUserDetail
  total: number
  page: number
  page_size: number
  items: SessionListItem[]
}

export interface AdminSessionDetailResponse {
  user: AdminUserDetail
  session: Session
}
