// TypeScript 类型定义

export interface User {
  id: number
  username: string
  email: string
  is_active: boolean
  created_at: string
}

export interface LoginRequest {
  username_or_email: string
  password: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
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
  provider?: string
  output_count?: number
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
  duration_ms: number
}

export interface ProviderCapabilities {
  supports_multi_image: boolean
  supports_mask: boolean
  supports_chat: boolean
  max_input_size_mb: number
  max_output_count: number
}

export interface ProviderInfo {
  name: string
  model: string
  display_name: string
  enabled: boolean
  capabilities: ProviderCapabilities
}

export interface ProvidersListResponse {
  default: string
  providers: ProviderInfo[]
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
