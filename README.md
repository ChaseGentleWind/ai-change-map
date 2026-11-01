# AI 图像编辑网站

基于 FastAPI、Vue 3 和 OpenAI 兼容图像接口的本地 AI 图像编辑应用。支持账号登录、参考图、局部涂抹、多轮编辑、历史记录、管理员管理和模型费用统计。

## 技术结构

- `backend/`：FastAPI API、认证、数据库、图像编辑服务和 Provider 实现
- `backend/providers/`：Provider 抽象、任务路由与 OpenAI、Gemini、SeedEdit 实现
- `backend/config/providers.yaml`：模型、路由、价格和分辨率配置
- `backend/routers/`：认证、编辑、历史/费用统计和管理员 API
- `backend/services/`：编辑、存储、历史和费用统计逻辑
- `backend/tests/`：后端 API、Provider、路由和费用统计测试
- `frontend/src/views/`：首页编辑器、登录、历史、个人中心和管理员页面
- `frontend/src/components/`：图片编辑、预览灯箱和编辑模式组件

## 本地启动

后端需要 Python 3.11 或更新版本。使用 Docker Desktop 启动本地 PostgreSQL，并安装依赖：

```powershell
docker compose up -d db
cd backend
copy .env.example .env
uv sync --locked
```

在 `backend/.env` 中配置 API 中转站地址和密钥、JWT 密钥及管理员账号。之后启动后端：

```powershell
.\.venv\Scripts\python.exe main.py
```

前端需要满足 Vite 要求的 Node.js 版本（Node.js 20.19+ 或 22.12+）：

```powershell
cd frontend
npm ci
npm run dev
```

默认地址：前端 `http://localhost:5174`，后端 `http://localhost:8001`，API 文档 `http://localhost:8001/docs`。Vite 将 `/api` 代理到后端。

## 模型配置

`backend/config/providers.yaml` 是模型配置来源。`image_model_picker.providers` 决定前端高级设置中可选的 Provider；每个 Provider 的 `model`、`supported_resolutions` 和 `price_per_image` 分别控制模型名、可选分辨率和单张人民币费用。首页默认使用 `openai_1k` / `gpt-image-2-1k` / `1k`。

Gemini 和 SeedEdit Provider 保留为可扩展实现；当前用户可选模型由上述白名单控制。Fallback 当前关闭。不要将 API 密钥提交到仓库。

## 主要 API

- `POST /api/auth/register`、`POST /api/auth/login`：注册和登录
- `GET /api/auth/me`、`PUT /api/auth/me/profile`、`PUT /api/auth/me/password`：个人账号
- `POST /api/edit`：图像编辑，支持指定 Provider、分辨率、参考图和遮罩
- `GET /api/history`、`GET /api/history/{session_id}`、`DELETE /api/history/{session_id}`：编辑历史
- `GET /api/usage?period=today|all`：按所选周期查看成功生成的图片数量和费用
- `/api/admin/*`：管理员用户及历史管理

## 验证

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm run build
```

## 数据与本地文件

用户、会话、编辑记录以及上传的原图、参考图、遮罩和生成结果都保存在数据库中。图片通过 `/api/assets/{id}` 从数据库读取，项目不再创建或读写本地 `uploads/`、`outputs/` 目录。

本地 Compose PostgreSQL 数据保存在 Docker volume `ai_change_map_db`。部署到 Ubuntu 时可新建数据库和 volume，项目会在启动时创建表；当前本地数据库和图片不需要迁移到服务器。SQLite 仍用于自动化测试，也可通过 `DATABASE_URL` 指向其他 SQLAlchemy 异步数据库。
