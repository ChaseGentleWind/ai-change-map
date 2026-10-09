# 图像 API 调用文档

本文档给第三方调用方使用，描述当前中转 API 的三类生图协议：

- `POST /v1/images/generations`：图像生成协议
- `POST /v1/images/edits`：图像编辑协议
- `POST /v1/chat/completions`：对话协议

## 与本项目的关系

本文档描述的是上游第三方 API 中转站协议，不是本项目 FastAPI 后端直接暴露给前端或业务调用方的 `/api/...` 接口。

本项目通过 `backend/providers/openai.py` 中的 `OpenAIProvider` 调用这些上游协议。项目 `.env` 中的 `OPENAI_BASE_URL` 应填写带 `/v1` 的基础地址，例如：

```text
OPENAI_BASE_URL=http://216.234.142.96:3000/v1
```

因为项目代码会在该基础地址后继续拼接 `/images/generations`、`/images/edits` 或 `/chat/completions`。

模型和调用模式建议：

- 默认高分辨率图片编辑：`OPENAI_MODEL=gpt-image2-Pro`，`providers.yaml` 中不配置 `request_mode`，项目会走 `/images/edits`。
- 1K 对话协议：`OPENAI_MODEL=gpt-image-2`，并在 `providers.yaml` 的 `openai` provider 下启用 `request_mode: chat_completions`。
- 纯文生图可使用 `/images/generations`；但本项目主业务接口 `/api/edit` 总会上传 `main_image`，默认会进入 `/images/edits`。

## 基础信息

默认基础地址：

```text
http://216.234.142.96:3000
```

如果接入本项目的 `OpenAIProvider`，请在 `.env` 中把 `OPENAI_BASE_URL` 配成带 `/v1` 的地址：

```text
OPENAI_BASE_URL=http://216.234.142.96:3000/v1
```

所有请求都需要携带 API Key：

```http
Authorization: Bearer <你的 API Key>
```

JSON 请求需要携带：

```http
Content-Type: application/json
```

高分辨率生图可能耗时较长，通常约 1 到 5 分钟，客户端超时时间建议设置为 10 分钟以上。

## 通用返回

图像生成协议与图像编辑协议通常返回 URL 结果，并包含用量信息：

```json
{
  "created": 1780829532,
  "data": [
    {
      "url": "https://oss.filenest.top/uploads/f02a7bee-53c7-46cd-a696-884eada4af7a.png"
    }
  ],
  "usage": {
    "total_tokens": 3356,
    "input_tokens": 20,
    "output_tokens": 3336,
    "input_tokens_details": {
      "text_tokens": 20,
      "image_tokens": 0
    }
  }
}
```

部分模型或上游通道也可能返回 base64：

```json
{
  "data": [
    {
      "b64_json": "iVBORw0KGgo..."
    }
  ]
}
```

调用方应同时兼容 `url` 和 `b64_json` 两种结果。

错误通常类似：

```json
{
  "error": {
    "message": "Invalid token",
    "type": "new_api_error",
    "code": "invalid_request"
  }
}
```

## 1. `/v1/images/generations`：图像生成协议

端点：

```http
POST /v1/images/generations
```

完整地址：

```text
http://216.234.142.96:3000/v1/images/generations
```

请求格式：`application/json`

### 参数

| 参数 | 类型 | 必填 | 示例 | 说明 |
| --- | --- | --- | --- | --- |
| `model` | string | 是 | `gpt-image2-Pro` | 模型名称 |
| `prompt` | string | 是 | `一只戴帽子的猫` | 生图提示词 |
| `size` | string | 否 | `3840x2160` | 输出尺寸 |
| `n` | integer | 否 | `1` | 生成张数，范围 `1` 到 `10` |

推荐模型：

```text
gpt-image2-Pro
```

常用尺寸：

```text
1024x1024
1536x1024
1024x1536
2048x2048
2048x1152
3840x2160
2160x3840
```

### curl 示例

```bash
curl http://216.234.142.96:3000/v1/images/generations \
  -H "Authorization: Bearer <你的 API Key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-image2-Pro",
    "prompt": "一只戴帽子的猫，电影感光影，高清细节",
    "size": "3840x2160",
    "n": 1
  }'
```

### JavaScript 示例

```js
const response = await fetch("http://216.234.142.96:3000/v1/images/generations", {
  method: "POST",
  headers: {
    Authorization: "Bearer <你的 API Key>",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    model: "gpt-image2-Pro",
    prompt: "一只戴帽子的猫，电影感光影，高清细节",
    size: "3840x2160",
    n: 1
  })
});

const data = await response.json();
console.log(data.data?.[0]?.url || data.data?.[0]?.b64_json);
```

### 响应示例

```json
{
  "created": 1780829532,
  "data": [
    {
      "url": "https://oss.filenest.top/uploads/f02a7bee-53c7-46cd-a696-884eada4af7a.png"
    }
  ],
  "usage": {
    "total_tokens": 3356,
    "input_tokens": 20,
    "output_tokens": 3336,
    "input_tokens_details": {
      "text_tokens": 20,
      "image_tokens": 0
    }
  }
}
```

调用方仍需兼容 `data[].b64_json`，部分模型或上游通道可能返回 base64 图片。

## 2. `/v1/images/edits`：图像编辑协议

端点：

```http
POST /v1/images/edits
```

完整地址：

```text
http://216.234.142.96:3000/v1/images/edits
```

图像编辑用于基于一张或多张参考图进行重绘、融合、局部修改或风格调整。

参考图限制：所有参考图总大小建议不要超过 20MB。

### 上传本地图片

请求格式：`multipart/form-data`

| 字段 | 类型 | 必填 | 示例 | 说明 |
| --- | --- | --- | --- | --- |
| `model` | string | 是 | `gpt-image2-Pro` | 模型名称，推荐使用 `gpt-image2-Pro` |
| `prompt` | string | 是 | `把人物背景改成雪山` | 编辑要求 |
| `size` | string | 否 | `2048x1152` | 输出尺寸 |
| `n` | integer | 否 | `1` | 生成张数，范围 `1` 到 `10` |
| `image[]` | file | 是 | `@ref1.png` | 图片文件，可重复传多张；第一张为主图/待编辑图，第二张起为参考图，总大小建议不超过 20MB |

推荐模型：

```text
gpt-image2-Pro
```

### curl 示例

```bash
curl http://216.234.142.96:3000/v1/images/edits \
  -H "Authorization: Bearer <你的 API Key>" \
  -F "model=gpt-image2-Pro" \
  -F "prompt=以第一张图为主体，参考第二张图的服装风格，生成一张自然合照" \
  -F "size=2048x1152" \
  -F "n=1" \
  -F "image[]=@./ref1.png" \
  -F "image[]=@./ref2.png"
```

### JavaScript 示例

```js
const form = new FormData();
form.append("model", "gpt-image2-Pro");
form.append("prompt", "以第一张图为主体，参考第二张图的服装风格，生成一张自然合照");
form.append("size", "2048x1152");
form.append("n", "1");
form.append("image[]", file1);
form.append("image[]", file2);

const response = await fetch("http://216.234.142.96:3000/v1/images/edits", {
  method: "POST",
  headers: {
    Authorization: "Bearer <你的 API Key>"
  },
  body: form
});

const data = await response.json();
console.log(data.data?.[0]?.url || data.data?.[0]?.b64_json);
```

### 携带本地参考图文件

编辑协议的图片不是写在 JSON 里的 URL 时，需要使用 `multipart/form-data` 上传本地文件。字段名使用 `image[]`，第一张 `image[]` 是主图/待编辑图，后续 `image[]` 是参考图。

单张参考图：

```bash
curl http://216.234.142.96:3000/v1/images/edits \
  -H "Authorization: Bearer <你的 API Key>" \
  -F "model=gpt-image2-Pro" \
  -F "prompt=保留人物主体，把背景改成雪山，整体保持自然光影" \
  -F "size=2048x1152" \
  -F "n=1" \
  -F "image[]=@./reference.png"
```

多张参考图：

```bash
curl http://216.234.142.96:3000/v1/images/edits \
  -H "Authorization: Bearer <你的 API Key>" \
  -F "model=gpt-image2-Pro" \
  -F "prompt=以第一张图的人物为主体，参考第二张图的服装和第三张图的背景风格生成新图" \
  -F "size=2048x1152" \
  -F "n=1" \
  -F "image[]=@./person.png" \
  -F "image[]=@./clothes.png" \
  -F "image[]=@./background.png"
```

Python 示例：

```python
import requests

url = "http://216.234.142.96:3000/v1/images/edits"
headers = {
    "Authorization": "Bearer <你的 API Key>"
}
data = {
    "model": "gpt-image2-Pro",
    "prompt": "参考第一张图的人物，结合第二张图的画面风格生成一张新图",
    "size": "2048x1152",
    "n": "1"
}
files = [
    ("image[]", ("person.png", open("./person.png", "rb"), "image/png")),
    ("image[]", ("style.png", open("./style.png", "rb"), "image/png")),
]

response = requests.post(url, headers=headers, data=data, files=files, timeout=600)
result = response.json()
print(result["data"][0].get("url") or result["data"][0].get("b64_json"))
```

注意：使用 `multipart/form-data` 时不要手动设置 `Content-Type`，让 HTTP 客户端自动生成带 boundary 的请求头。所有参考图总大小建议不要超过 20MB。

### 响应示例

```json
{
  "created": 1780829532,
  "data": [
    {
      "url": "https://oss.filenest.top/uploads/f02a7bee-53c7-46cd-a696-884eada4af7a.png"
    }
  ],
  "usage": {
    "total_tokens": 3356,
    "input_tokens": 20,
    "output_tokens": 3336,
    "input_tokens_details": {
      "text_tokens": 20,
      "image_tokens": 0
    }
  }
}
```

调用方仍需兼容 `data[].b64_json`，部分模型或上游通道可能返回 base64 图片。

### 使用图片 URL 或文件 ID

如果调用方不方便上传文件，也可以尝试 JSON 方式传图片引用：

```bash
curl http://216.234.142.96:3000/v1/images/edits \
  -H "Authorization: Bearer <你的 API Key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-image2-Pro",
    "prompt": "参考这些图片，生成一张自然的全家福",
    "size": "2048x1152",
    "n": 1,
    "images": [
      "https://example.com/ref1.png",
      "https://example.com/ref2.png"
    ]
  }'
```

优先推荐 `multipart/form-data` 上传本地图片，兼容性更好。JSON `images` 方式属于中转站可选能力；当前本项目 `OpenAIProvider` 未使用该路径，项目默认使用 `multipart/form-data` 的 `image[]` 字段。

## 3. /v1/chat/completions：对话协议

端点：

```http
POST /v1/chat/completions
```

完整地址：

```text
http://216.234.142.96:3000/v1/chat/completions
```

该协议使用 Chat Completions 的消息结构承载提示词和参考图，仅用于 1K 生图模型 `gpt-image-2`。

### 参数

| 参数 | 类型 | 必填 | 示例 | 说明 |
| --- | --- | --- | --- | --- |
| `model` | string | 是 | `gpt-image-2` | 1K 生图模型 |
| `messages` | array | 是 | 见下方示例 | 消息数组 |
| `size` | string | 否 | `1536x1024` | 输出尺寸 |
| `n` | integer | 否 | `1` | 生成张数，范围 `1` 到 `10`；不传默认 `1` |
| `stream` | boolean | 否 | `false` | 建议默认 `false` |

1K 常用模型：

```text
gpt-image-2
```

1K 常用尺寸：

```text
方图 1254x1254
横图 1448x1086
竖图 1086x1448
横图 1536x1024
竖图 1024x1536
```

自定义尺寸要求：宽度和高度都必须能被 16 整除；短边不能小于 512，长边不能超过 1536；请求的宽高比必须介于 `1:3` 和 `3:1` 之间。

### 纯文本生图

```bash
curl http://216.234.142.96:3000/v1/chat/completions \
  -H "Authorization: Bearer <你的 API Key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-image-2",
    "stream": false,
    "size": "1536x1024",
    "n": 1,
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "生成一张温暖的儿童绘本风格小屋插画。Generate exactly one image asset. Return only the image result."
          }
        ]
      }
    ]
  }'
```

### 携带参考图

参考图使用 `image_url` 放在 `messages.content` 中，可以传 HTTP 图片地址，也可以传 `data:image/...;base64,...`。所有参考图总大小建议不要超过 20MB。

注意：`/v1/chat/completions` 必须使用 `application/json` 请求。不要用 `multipart/form-data` 直接传图片文件，否则上游可能无法解析 `model`、`messages` 等字段。调用方如果只有本地图片文件，需要先把图片转成 `data:image/...;base64,...`，再放到 `image_url.url`。

```bash
curl http://216.234.142.96:3000/v1/chat/completions \
  -H "Authorization: Bearer <你的 API Key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-image-2",
    "stream": false,
    "size": "1536x1024",
    "n": 1,
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "参考图片中的人物，生成一张自然的半身肖像。Generate exactly one image asset. Return only the image result."
          },
          {
            "type": "image_url",
            "image_url": {
              "url": "https://example.com/reference.png"
            }
          }
        ]
      }
    ]
  }'
```

### 使用多张参考图

多张参考图继续在同一个 `messages[].content[]` 数组中追加多个 `image_url` 内容块。可以混合使用 HTTP 图片地址和 `data:image/...;base64,...`，但所有参考图总大小建议不要超过 20MB。

```bash
curl http://216.234.142.96:3000/v1/chat/completions \
  -H "Authorization: Bearer <你的 API Key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-image-2",
    "stream": false,
    "size": "1024x1536",
    "n": 1,
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "以第一张图的人物为主体，参考第二张图的服装风格和第三张图的背景氛围，生成一张自然人像。Generate exactly one image asset. Return only the image result."
          },
          {
            "type": "image_url",
            "image_url": {
              "url": "https://example.com/person.png"
            }
          },
          {
            "type": "image_url",
            "image_url": {
              "url": "https://example.com/clothes-style.png"
            }
          },
          {
            "type": "image_url",
            "image_url": {
              "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
            }
          }
        ]
      }
    ]
  }'
```

本地图片转成 data URL 后的写法示例：

```json
{
  "model": "gpt-image-2",
  "stream": false,
  "size": "1024x1536",
  "n": 1,
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "参考上传图片，生成一张自然的人像照片。Generate exactly one image asset. Return only the image result."
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
          }
        }
      ]
    }
  ]
}
```

浏览器中把本地文件转成 data URL：

```js
function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

const imageUrl = await fileToDataUrl(file);
```

### Chat 协议返回解析

中转站可能会把 Chat Completions 的原始响应标准化成统一图片结构。调用方优先读取顶层 `data[].url`；如需排查原始响应，可查看 `responses[]`。

如果请求中设置 `n > 1`，中转站会返回多张图片：`data[]` 会按生成结果平铺，`responses[]` 会保留每次 Chat Completions 的原始响应；可以通过 `data[].response_index` 对应到 `responses[]` 的下标。

示例返回：

```json
{
  "object": "image_generation",
  "model": "gpt-image-2",
  "size": "1024x1536",
  "data": [
    {
      "url": "https://oss.filenest.top/uploads/8e9c0044-145f-4336-887d-6059c28ec3aa.png",
      "response_index": 0,
      "image_index": 0
    }
  ],
  "responses": [
    {
      "id": "chatcmpl-c372ab09-5790-4eb1-890d-5dd83accc69c",
      "object": "chat.completion",
      "created": 1779777013,
      "model": "gpt-image-2",
      "choices": [
        {
          "index": 0,
          "message": {
            "role": "assistant",
            "content": "![image](https://oss.filenest.top/uploads/8e9c0044-145f-4336-887d-6059c28ec3aa.png)\n\n"
          },
          "finish_reason": "stop"
        }
      ],
      "usage": {
        "prompt_tokens": 26,
        "completion_tokens": 1145,
        "total_tokens": 1171
      }
    }
  ]
}
```

如果调用方直接对接原始 `/v1/chat/completions`，也可以按以下顺序兜底解析图片：

1. `choices[].message.content[]` 中的 `image_url.url`
2. `choices[].message.content` 文本里的 Markdown 图片地址
3. `choices[].message.content` 文本里的普通 HTTP 图片地址
4. `data[].url`
5. `data[].b64_json`

注意：本项目后端不会把上游 `responses[]` 原样返回给前端。项目会提取上游返回的 `url` 或 `b64_json`，保存为本地静态文件，并在 `/api/edit` 响应的 `results[]` 中返回 `/outputs/...` 地址。

## 本项目接入注意

- 本项目业务接口使用项目自己的 JWT 登录 token，不会向前端暴露中转站 API Key。
- 本项目 `/api/edit` 是业务封装接口，字段名是 `main_image`、`instruction`、`reference_images`、`mask_image`、`output_count` 等，不是上游中转站的 `prompt`、`image[]`。
- 上游中转站返回 `url` 或 `b64_json` 后，项目会下载或解码图片，保存到 `outputs/`，再通过 FastAPI StaticFiles 返回 `/outputs/...` 静态文件 URL。

## 调用建议

- 高分辨率请求可能耗时 1 到 5 分钟，客户端不要设置过短超时。
- 同一个请求如果已经提交成功但客户端超时，不建议立刻无限重试，避免重复扣费。
- 所有参考图总大小建议不要超过 20MB。
- 图片编辑优先使用 `multipart/form-data` 上传 `image[]`。
- `/v1/chat/completions` 不要使用 `multipart/form-data` 上传本地图片；本地图片请转成 `data:image/...;base64,...` 后放到 `image_url.url`。
- 暂不建议传 `response_format`、`quality`、`style`、`mask`、`stream=true` 等未确认参数。
- 保存返回的 `url` 时应尽快下载到自己的存储，远程图片链接可能有过期时间。
