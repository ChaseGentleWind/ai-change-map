# AI 图像编辑网站

基于 Gemini / OpenAI 的图像编辑服务，支持参考图编辑、文字替换、去水印等功能。

## 技术栈

**后端：**
- FastAPI + Python 3.11+
- SQLite + SQLAlchemy
- Provider 抽象层（支持 Gemini / OpenAI / 通义万相 / FLUX 等）

**前端：**
- Vue 3 + TypeScript
- Vite + TailwindCSS
- Vue Router + Axios

## 核心特性

- ✅ **Provider 抽象层** — 模型可插拔，配置文件驱动
- ✅ **智能路由** — 根据任务类型自动选择最合适的模型
- ✅ **多轮对话式编辑** — ChatGPT 风格，同一会话连续修改
- ✅ **自动 Fallback** — 主模型失败时自动切换备用
- ✅ **历史记录** — 服务器端 SQLite 存储

## 快速开始

### 1. 后端启动

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的 API Key 和中转站地址

# 启动服务
python main.py
# 或
uvicorn main:app --reload --port 8001
```

后端将运行在 `http://localhost:8001`

API 文档：`http://localhost:8001/docs`

### 2. 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端将运行在 `http://localhost:5174`

## 配置说明

### 环境变量 (.env)

```env
# API 中转站配置
RELAY_API_BASE=https://your-relay-api.com/v1
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# 数据库
DATABASE_URL=sqlite+aiosqlite:///./db/app.db
```

### Providers 配置 (backend/config/providers.yaml)

```yaml
default_provider: openai

providers:
  gemini:
    enabled: false
    api_base: "${RELAY_API_BASE}"
    api_key: "${GEMINI_API_KEY}"
    model: "gemini-2.5-flash-image"
    timeout: 60

  openai:
    enabled: true
    api_base: "${RELAY_API_BASE}"
    api_key: "${OPENAI_API_KEY}"
    model: "gpt-image-2"
    timeout: 60

routing:
  text_edit: openai
  watermark_remove: openai
  reference_edit: openai
  iterative_edit: openai
  default: openai
  iterative_edit: gemini     # 多轮对话用 Gemini
  default: gemini

fallback:
  enabled: true
  chain:
    gemini: [openai]
    openai: [gemini]
  max_retries: 1

session:
  max_context_turns: 10
```

## 使用示例

### 1. 参考图编辑

上传主图 + 参考图，输入指令：
```
把图1中的椅子换成图2中的款式，其他保持不变
```

### 2. 文字替换

上传海报图，输入指令：
```
把广告牌上的"促销"改成"特价"，保持原有字体和颜色
```

### 3. 去水印

上传带水印的图片，输入指令：
```
去掉右下角的水印，保持背景纹理自然
```

### 4. 多轮迭代编辑

第一轮：`把椅子换成红色`
第二轮：`再把墙刷成蓝色`
第三轮：`加一盏台灯`

## 项目结构

```
ai-change-map/
├── backend/
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # 配置加载
│   ├── database.py             # 数据库连接
│   ├── routers/                # API 路由
│   │   ├── edit.py             # 编辑接口
│   │   ├── history.py          # 历史记录
│   │   └── providers.py        # Providers 信息
│   ├── providers/              # Provider 抽象层
│   │   ├── base.py             # 抽象基类
│   │   ├── schemas.py          # 数据契约
│   │   ├── registry.py         # 注册器
│   │   ├── router.py           # 智能路由
│   │   ├── gemini.py           # Gemini 实现
│   │   └── openai.py           # OpenAI 实现
│   ├── services/               # 业务服务
│   │   └── storage.py          # 文件存储
│   ├── models/                 # 数据模型
│   │   ├── database.py         # ORM 模型
│   │   └── schemas.py          # API 模型
│   └── config/
│       └── providers.yaml      # Providers 配置
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── Home.vue        # 主编辑页
│   │   │   └── History.vue     # 历史记录页
│   │   ├── api/
│   │   │   └── index.ts        # API 调用
│   │   ├── types/
│   │   │   └── index.ts        # 类型定义
│   │   └── router/
│   │       └── index.ts        # 路由配置
│   └── package.json
├── uploads/                    # 上传图片
├── outputs/                    # 生成结果
└── README.md
```

## API 接口

### POST /api/edit
图像编辑接口

**请求：** `multipart/form-data`
- `main_image`: 主图文件
- `instruction`: 编辑指令
- `session_id`: 会话 ID（可选）
- `parent_id`: 父记录 ID（可选）
- `provider`: 手动指定 provider（可选）
- `output_count`: 生成数量（默认 1）
- `reference_images[]`: 参考图（可选）

**响应：**
```json
{
  "record_id": 123,
  "session_id": "uuid-xxx",
  "provider": "gemini",
  "model": "gemini-2.5-flash-image",
  "task_type": "reference_edit",
  "results": ["/outputs/xxx_1.png"],
  "usage": {...},
  "cost": 0.039,
  "duration_ms": 8200
}
```

### GET /api/providers
获取可用 providers 列表

### GET /api/history
获取会话列表（分页）

### GET /api/history/{session_id}
获取单个会话详情

### DELETE /api/history/{session_id}
删除会话

## 扩展新 Provider

1. 在 `backend/providers/` 下创建新文件，如 `tongyi.py`
2. 继承 `ImageEditorProvider` 并实现 `edit()` 和 `capabilities()` 方法
3. 使用 `@register("tongyi")` 装饰器注册
4. 在 `providers.yaml` 中添加配置
5. 在 `providers/__init__.py` 中导入

示例：
```python
from .base import ImageEditorProvider
from .registry import register

@register("tongyi")
class TongyiProvider(ImageEditorProvider):
    def capabilities(self):
        return Capabilities(...)

    async def edit(self, request):
        # 实现调用逻辑
        ...
```

## 常见问题

**Q: 如何切换默认模型？**
A: 修改 `providers.yaml` 中的 `default_provider` 字段

**Q: 如何禁用某个 provider？**
A: 在 `providers.yaml` 中将对应 provider 的 `enabled` 设为 `false`

**Q: 如何调整智能路由规则？**
A: 修改 `providers.yaml` 中的 `routing` 部分，或在 `providers/router.py` 中调整关键词识别逻辑

**Q: 如何增加会话上下文轮数？**
A: 修改 `providers.yaml` 中的 `session.max_context_turns` 值

## License

MIT
