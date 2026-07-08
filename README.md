# AI 图像编辑网站

这是一个基于 FastAPI + Vue 3 的 AI 图像编辑网站。用户上传原图后，可以通过自然语言指令、参考图、局部涂抹 mask 或文字图层完成图像修改，并支持多轮会话、历史记录和管理员查看。

## 当前能力

- 用户注册、登录、JWT 鉴权、个人资料和密码修改
- 主图上传、参考图上传、自然语言图像编辑
- 通用编辑、局部涂抹编辑、文字图层合成三种工作流
- 多轮编辑：可基于上一轮结果继续修改
- 历史会话：按用户保存原图、结果图、指令、模型、耗时和成本估算
- 管理后台：管理员可查看用户、用户历史、会话详情并删除会话
- Provider 抽象层：支持 OpenAI 兼容图像接口、Gemini、SeedEdit 等 provider
- 文件存储：上传文件在 `uploads/`，生成结果在 `outputs/`

## 技术栈

后端：

- Python 3.11+
- FastAPI
- SQLAlchemy async + SQLite
- httpx、Pillow、python-dotenv、PyYAML

前端：

- Vue 3
- TypeScript
- Vite
- Tailwind CSS
- Vue Router
- Axios

## 快速启动

### 一键启动开发环境

项目根目录已经支持双击启动：

```text
start-all.bat
```

双击后会自动调用 PowerShell 启动后端、前端和 ngrok，并在窗口里显示 ngrok 公网地址。地址会自动复制到剪贴板。

停止服务时双击：

```text
stop-all.bat
```

也可以在命令行启动：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-all.ps1
```

脚本会启动：

- 后端：`http://localhost:8001`
- 前端：`http://localhost:5174`
- ngrok：自动执行 `ngrok http 5174`

脚本默认寻找项目根目录下的 `ngrok.exe`。如果你的 ngrok 放在其它位置，可以这样指定：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-all.ps1 -NgrokPath "D:\tools\ngrok.exe"
```

启动日志和 PID 文件会写入 `.runtime/`。

### 手动启动后端

```powershell
cd backend

# 首次使用时创建 .env
copy .env.example .env

# 推荐使用已有 .venv；如果没有，请先安装 pyproject.toml 中的依赖
.\.venv\Scripts\python.exe main.py
```

后端默认运行在 `http://localhost:8001`，API 文档在：

```text
http://localhost:8001/docs
```

### 手动启动前端

```powershell
cd frontend
npm install
npm run dev
```

前端默认运行在：

```text
http://localhost:5174
```

Vite 已配置代理：

- `/api` -> `http://localhost:8001`
- `/uploads` -> `http://localhost:8001`
- `/outputs` -> `http://localhost:8001`

## 环境变量

后端读取 `backend/.env`。常用配置如下：

```env
# OpenAI 兼容中转站
OPENAI_BASE_URL=https://ainx.chat/v1
OPENAI_API_KEY=your_openai_compatible_api_key_here
OPENAI_MODEL=gpt-image-2-1k

# Gemini / SeedEdit 相关中转站
YUNWU_API_BASE=https://yunwu.ai/v1
YUNWU_GEMINI_API_BASE=https://yunwu.ai/v1beta
YUNWU_API_KEY=your_yunwu_api_key_here

# 兼容旧变量
RELAY_API_BASE=https://ainx.chat/v1
GEMINI_API_KEY=your_yunwu_api_key_here
AINX_API_BASE=https://ainx.chat/v1
AINX_API_KEY=your_ainx_api_key_here

# 数据库
DATABASE_URL=sqlite+aiosqlite:///./db/app.db

# 服务端口
PORT=8001

# JWT，生产环境必须替换为长度 >= 32 的随机字符串
JWT_SECRET_KEY=please_change_this_secret_in_production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=10080

# 自动创建/同步管理员账号
ADMIN_USERNAME=superadmin
ADMIN_PHONE=13900000000
ADMIN_PASSWORD=please_change_admin_password

# 额外管理员白名单
ADMIN_USERNAMES=
ADMIN_PHONES=

# CORS 白名单
CORS_ALLOWED_ORIGINS=http://localhost:5174
```

生成安全 JWT 密钥：

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

## Provider 配置

Provider 配置位于 `backend/config/providers.yaml`。当前默认配置以 `openai_1k` 为主：

```yaml
default_provider: openai_1k

routing:
  text_edit: openai_1k
  watermark_remove: openai_1k
  reference_edit: openai_1k
  iterative_edit: openai_1k
  default: openai_1k

fallback:
  enabled: false
```

当前已注册的 provider：

- `openai_1k`：GPT-Image-2 1K，走 `/images/edits`
- `openai_pro4k`：GPT-Image2 Pro 4K，支持 1K/2K/4K 档位
- `openai_chat`：GPT-Image-2，走 `/chat/completions`
- `gemini`：Gemini 2.5 Flash Image
- `seededit`：豆包 SeedEdit 3.0 i2i

新增 provider 的步骤：

1. 在 `backend/providers/` 下新增实现文件
2. 继承 `ImageEditorProvider`
3. 实现 `edit()` 和 `capabilities()`
4. 使用 `@register("provider_name")` 注册
5. 在 `backend/providers/__init__.py` 导入
6. 在 `backend/config/providers.yaml` 添加配置

## 主要接口

### 认证

- `POST /api/auth/register`：注册
- `POST /api/auth/login`：登录
- `GET /api/auth/me`：当前用户
- `PUT /api/auth/me/profile`：修改资料
- `PUT /api/auth/me/password`：修改密码

### 图像编辑

`POST /api/edit`

请求类型：`multipart/form-data`

字段：

- `main_image`：主图，必填
- `instruction`：编辑指令，必填
- `session_id`：会话 ID，可选
- `parent_id`：父编辑记录 ID，可选
- `parent_result_index`：继续编辑父记录的第几张结果图，默认 `0`
- `provider`：手动指定 provider，可选
- `output_count`：生成数量
- `output_resolution`：输出分辨率档位，`1k` / `2k` / `4k`
- `task_mode`：`general` / `local_edit` / `text_layer`
- `edit_metadata`：前端编辑状态 JSON
- `reference_images`：参考图，可多张
- `mask_image`：局部编辑 mask

响应示例：

```json
{
  "record_id": 123,
  "session_id": "uuid-xxx",
  "provider": "openai_1k",
  "model": "gpt-image-2-1k",
  "task_type": "reference_edit",
  "fallback_used": null,
  "results": ["/outputs/xxxx.png"],
  "usage": {
    "input_tokens": 0,
    "output_tokens": 0,
    "total_tokens": 0
  },
  "cost": null,
  "duration_ms": 8200
}
```

### 历史记录

- `GET /api/history`：当前用户会话列表
- `GET /api/history/{session_id}`：当前用户会话详情
- `DELETE /api/history/{session_id}`：删除当前用户会话

### Providers

- `GET /api/providers`：可用 provider 列表和能力信息

### 管理员

- `GET /api/admin/users`：用户列表
- `GET /api/admin/users/{user_id}`：用户详情
- `PUT /api/admin/users/{user_id}`：修改用户
- `GET /api/admin/users/{user_id}/history`：指定用户历史
- `GET /api/admin/history/{session_id}`：任意会话详情
- `DELETE /api/admin/history/{session_id}`：删除任意会话

## 项目结构

```text
ai-change-map/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── auth.py
│   ├── config/
│   │   └── providers.yaml
│   ├── models/
│   │   ├── database.py
│   │   └── schemas.py
│   ├── providers/
│   │   ├── base.py
│   │   ├── schemas.py
│   │   ├── registry.py
│   │   ├── router.py
│   │   ├── openai.py
│   │   ├── gemini.py
│   │   └── seededit.py
│   ├── routers/
│   │   ├── auth.py
│   │   ├── admin.py
│   │   ├── edit.py
│   │   ├── history.py
│   │   └── providers.py
│   ├── services/
│   │   ├── edit_service.py
│   │   ├── history.py
│   │   ├── storage.py
│   │   └── admin_bootstrap.py
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── router/
│   │   ├── stores/
│   │   ├── types/
│   │   └── views/
│   ├── package.json
│   └── vite.config.ts
├── uploads/
├── outputs/
├── ngrok.exe
├── start-all.bat
├── start-all.ps1
├── stop-all.bat
└── README.md
```

## 测试

后端测试：

```powershell
cd backend
python -m pytest -q
```

前端构建：

```powershell
cd frontend
npm run build
```

## 常见问题

**启动时报 JWT_SECRET_KEY 不安全**

修改 `backend/.env` 中的 `JWT_SECRET_KEY`，使用长度大于等于 32 的随机字符串。

**ngrok 打开后页面提示 Host 不允许**

前端 `vite.config.ts` 已加入常见 ngrok 域名白名单。如果你使用固定自定义域名，也可以把域名加入 `server.allowedHosts`。

**如何切换默认模型**

修改 `backend/config/providers.yaml` 的 `default_provider` 和 `routing`。

**如何启用 fallback**

修改 `backend/config/providers.yaml`：

```yaml
fallback:
  enabled: true
```

并确认 fallback 链中的 provider 都已配置 API Key 且 `enabled: true`。

## License

MIT
