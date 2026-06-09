# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## 项目概述

AI 图像编辑网站，核心功能是基于原图进行精准局部修改（参考图替换、文字替换、去水印等），保持图片其他部分不变。

## 启动命令

### 后端
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # 填入 RELAY_API_BASE / GEMINI_API_KEY / OPENAI_API_KEY
python main.py         # 或 uvicorn main:app --reload --port 8001
```
API 文档：`http://localhost:8001/docs`

### 前端
```bash
cd frontend
npm install
npm run dev            # http://localhost:5174
npm run build          # 生产构建
```

Vite 已配置代理：`/api`、`/uploads`、`/outputs` 均转发到 `http://localhost:8001`。

## 


### Provider 抽象层（核心设计）

`backend/providers/` 是整个项目的核心，实现了模型可插拔架构：

```
base.py       → ImageEditorProvider 抽象基类（edit / capabilities / chat_edit）
schemas.py    → 统一数据契约（EditRequest / EditResponse / Capabilities）
registry.py   → @register 装饰器 + PROVIDERS 全局注册表 + get_provider 工厂
router.py     → TaskRouter：关键词识别任务类型 → 选择最合适的 provider
gemini.py     → Gemini 2.5 Flash Image 实现（多图 + 多轮对话）
openai.py     → GPT-Image-1 实现（文字渲染最强）
__init__.py   → 导入所有 provider 以触发 @register 注册
```

**新增 Provider 的步骤**：实现 `ImageEditorProvider` 子类 → 加 `@register("name")` → 在 `__init__.py` 导入 → 在 `providers.yaml` 添加配置。

### 智能路由规则

`providers/router.py` 的 `TaskRouter.detect_task_type()` 按优先级识别：
1. 有 `parent_id` → `iterative_edit`（Gemini）
2. 有参考图 → `reference_edit`（Gemini）
3. 指令含"文字/字/text/写/改成/替换" → `text_edit`（OpenAI）
4. 指令含"水印/logo/标志/去掉/去除/移除" → `watermark_remove`（Gemini）
5. 其他 → `default`（Gemini）

路由规则在 `backend/config/providers.yaml` 的 `routing` 节可配置。

### 数据流

```
POST /api/edit (multipart)
  → routers/edit.py
  → TaskRouter.select_provider()
  → get_provider(name, config)
  → provider.edit(EditRequest)
  → services/storage.save_outputs()
  → 写入 EditRecord (SQLite)
  → 返回 EditResponseSchema
```

### 数据库模型

- `EditSession`：一次上传对应一个会话，包含原始主图 URL
- `EditRecord`：每轮编辑一条记录，通过 `parent_id` 形成编辑链，`session_id` 关联会话

### 配置系统

`backend/config.py` 加载 `config/providers.yaml`，自动替换 `${ENV_VAR}` 占位符为环境变量值。`PROVIDERS_CONFIG` 全局变量在整个后端共享。

Fallback 配置在 `providers.yaml` 的 `fallback.chain` 中定义，`routers/edit.py` 在 provider 调用失败时自动执行。

### 前端结构

- `src/views/Home.vue`：主编辑页，包含上传、指令输入、多轮对话历史、结果展示全部逻辑
- `src/views/History.vue`：历史会话列表页
- `src/api/index.ts`：所有 API 调用封装（axios，120s 超时）
- `src/types/index.ts`：与后端 Pydantic 模型对应的 TypeScript 类型

## 关键约定

- **代码注释和 UI 文案全部使用中文**
- 所有模型通过第三方 API 中转站调用，`RELAY_API_BASE` 为中转站地址，兼容 OpenAI 格式（OpenRouter / one-api 等）
- 单会话最多保留 10 轮上下文（`providers.yaml` 的 `session.max_context_turns`）
- 文件存储：上传图在 `uploads/`，生成结果在 `outputs/`，均通过 FastAPI StaticFiles 提供访问
