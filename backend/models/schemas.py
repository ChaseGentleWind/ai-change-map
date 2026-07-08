"""API 请求/响应 Pydantic 模型"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class UserSchema(BaseModel):
    """当前登录用户信息。"""
    id: int
    username: str
    phone: Optional[str] = None
    is_active: bool
    is_admin: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class RegisterRequestSchema(BaseModel):
    """注册请求。"""
    username: str = Field(..., min_length=1, max_length=15)
    phone: str = Field(..., min_length=11, max_length=11)
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequestSchema(BaseModel):
    """登录请求。"""
    username_or_phone: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class UpdateProfileRequestSchema(BaseModel):
    """修改个人资料请求。"""
    username: str = Field(..., min_length=1, max_length=15)
    phone: str = Field(..., min_length=11, max_length=11)


class UpdatePasswordRequestSchema(BaseModel):
    """修改密码请求。"""
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


class AuthResponseSchema(BaseModel):
    """登录/注册响应。"""
    access_token: str
    token_type: str = "bearer"
    user: UserSchema


class EditRequestSchema(BaseModel):
    """编辑请求（JSON 部分，图片通过 multipart 传）"""
    instruction: str = Field(..., description="自然语言编辑指令")
    session_id: Optional[str] = Field(None, description="会话 ID，不传则创建新会话")
    parent_id: Optional[int] = Field(None, description="父记录 ID（迭代编辑用）")
    parent_result_index: int = Field(0, ge=0, description="父记录结果图索引")
    provider: Optional[str] = Field(None, description="手动指定 provider，不传走智能路由")
    output_count: int = Field(1, ge=1, le=10, description="生成数量")
    output_resolution: Optional[str] = Field(None, description="输出分辨率档位：1k/2k/4k")


class EditResponseSchema(BaseModel):
    """编辑响应"""
    record_id: int
    session_id: str
    provider: str
    model: str
    task_type: str
    fallback_used: Optional[str] = None
    results: List[str]
    usage: Dict[str, int]
    cost: Optional[float] = None
    duration_ms: int


class ProviderCapabilitiesSchema(BaseModel):
    """Provider 能力"""
    supports_multi_image: bool
    supports_mask: bool
    supports_chat: bool
    max_input_size_mb: int
    max_output_count: int


class ProviderInfoSchema(BaseModel):
    """Provider 信息"""
    name: str
    model: str
    display_name: str
    enabled: bool
    capabilities: ProviderCapabilitiesSchema


class ProvidersListSchema(BaseModel):
    """Provider 列表响应"""
    default: str
    providers: List[ProviderInfoSchema]


class RecordSchema(BaseModel):
    """编辑记录"""
    id: int
    session_id: str
    parent_id: Optional[int]
    main_image_url: str
    reference_urls: Optional[List[str]]
    mask_url: Optional[str] = None
    edit_metadata: Optional[Dict[str, Any]] = None
    instruction: str
    task_type: Optional[str]
    provider: str
    model: str
    fallback_used: Optional[str]
    result_urls: Optional[List[str]]
    status: str
    error_message: Optional[str]
    cost: Optional[float]
    duration_ms: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class SessionSchema(BaseModel):
    """会话信息"""
    id: str
    title: Optional[str]
    original_url: str
    records: List[RecordSchema] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SessionListItemSchema(BaseModel):
    """会话列表项"""
    id: str
    title: Optional[str]
    original_url: str
    last_result_url: Optional[str]
    record_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SessionListSchema(BaseModel):
    """会话列表响应"""
    total: int
    page: int
    page_size: int
    items: List[SessionListItemSchema]


class AdminUserListItemSchema(BaseModel):
    """管理员用户列表项。"""
    id: int
    username: str
    phone: Optional[str] = None
    is_active: bool
    is_admin: bool
    session_count: int
    record_count: int
    last_active_at: Optional[datetime] = None
    created_at: datetime


class AdminUserListSchema(BaseModel):
    """管理员用户列表响应。"""
    total: int
    page: int
    page_size: int
    items: List[AdminUserListItemSchema]


class AdminUserDetailSchema(AdminUserListItemSchema):
    """管理员用户详情。"""
    pass


class AdminUpdateUserRequestSchema(BaseModel):
    """管理员修改用户请求。"""
    username: str = Field(..., min_length=1, max_length=15)
    phone: str = Field(..., min_length=11, max_length=11)
    is_active: bool


class AdminUserHistorySchema(BaseModel):
    """管理员查看指定用户历史响应。"""
    user: AdminUserDetailSchema
    total: int
    page: int
    page_size: int
    items: List[SessionListItemSchema]


class AdminSessionDetailSchema(BaseModel):
    """管理员查看会话详情响应。"""
    user: AdminUserDetailSchema
    session: SessionSchema
