"""SeedEdit Provider 实现（豆包 SeedEdit 3.0 i2i）"""
import httpx
import base64
from .base import ImageEditorProvider
from .schemas import EditRequest, EditResponse, Capabilities, TokenUsage
from .registry import register


@register("seededit")
class SeedEditProvider(ImageEditorProvider):
    """字节跳动 SeedEdit 3.0 i2i Provider，走云雾中转的 OpenAI 兼容 /v1/images/generations 接口"""

    def capabilities(self) -> Capabilities:
        return Capabilities(
            supports_multi_image=False,
            supports_mask=False,
            supports_chat=False,
            max_input_size_mb=10,
            max_output_count=1
        )

    async def edit(self, request: EditRequest) -> EditResponse:
        """
        调用 SeedEdit 进行图像编辑。

        SeedEdit 在云雾走 OpenAI 兼容协议：JSON body，image 用 data URL（base64）。
        不支持参考图、不支持多轮历史；多轮场景由前端将上一轮结果回填为 main_image 实现。
        """
        # 主图编码为 data URL
        main_b64 = base64.b64encode(request.main_image).decode("utf-8")
        image_data_url = f"data:image/png;base64,{main_b64}"

        url = f"{self.api_base}/images/generations"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "prompt": request.instruction,
            "image": image_data_url,
            "size": "adaptive",
            "guidance_scale": 5.5,
            "watermark": False,
            "response_format": "url",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", response.text)
                except Exception:
                    error_msg = response.text
                raise Exception(f"SeedEdit API 错误 {response.status_code}: {error_msg}")

            result = response.json()

        # 解析响应：兼容 url / b64_json 两种格式
        images = []
        for item in result.get("data", []):
            if "b64_json" in item:
                images.append(base64.b64decode(item["b64_json"]))
            elif "url" in item:
                async with httpx.AsyncClient(timeout=30) as dl_client:
                    img_response = await dl_client.get(item["url"])
                    img_response.raise_for_status()
                    images.append(img_response.content)

        usage_data = result.get("usage", {}) or {}
        usage = TokenUsage(
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        return EditResponse(
            images=images,
            usage=usage,
            provider="seededit",
            model=self.model,
            raw_response=result,
        )
