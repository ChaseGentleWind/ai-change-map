"""ORM 数据库模型"""
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from database import Base


class EditSession(Base):
    """编辑会话表 — 一个会话对应一组多轮对话"""
    __tablename__ = "edit_sessions"

    id = Column(String(36), primary_key=True)  # UUID
    title = Column(String(200), nullable=True)  # 会话标题（取第一条指令前20字）
    original_url = Column(Text, nullable=False)  # 原始主图路径
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class EditRecord(Base):
    """编辑记录表 — 每一轮编辑对应一条记录"""
    __tablename__ = "edit_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("edit_sessions.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("edit_records.id"), nullable=True)  # 上一轮记录 ID

    # 输入
    main_image_url = Column(Text, nullable=False)   # 本轮编辑的主图（可能是上一轮结果）
    reference_urls = Column(Text, nullable=True)    # 参考图路径 JSON 数组
    mask_url = Column(Text, nullable=True)          # mask 路径
    edit_metadata = Column(Text, nullable=True)     # 前端编辑状态 JSON
    instruction = Column(Text, nullable=False)      # 用户指令

    # 路由信息
    task_type = Column(String(50), nullable=True)   # 识别出的任务类型
    provider = Column(String(50), nullable=False)   # 实际使用的 provider
    model = Column(String(100), nullable=False)     # 实际使用的模型
    fallback_used = Column(String(50), nullable=True)  # 若触发 fallback，记录原始 provider

    # 输出
    result_urls = Column(Text, nullable=True)       # 结果图路径 JSON 数组
    status = Column(String(20), default="pending")  # pending/completed/failed
    error_message = Column(Text, nullable=True)

    # 统计
    token_usage = Column(Text, nullable=True)       # token 用量 JSON
    cost = Column(Float, nullable=True)             # 估算成本（美元）
    duration_ms = Column(Integer, nullable=True)    # 耗时毫秒

    created_at = Column(DateTime, server_default=func.now())
