# utils/huawei/core/huawei_api_client.py
import time
import hmac
import hashlib
import base64
import aiohttp
from typing import Optional, Dict, Any
from urllib.parse import urlparse, quote

class HuaweiApiClient:
    """
    华为云 API 基类
    提供：
    - AK/SK 管理
    - 基础签名能力
    - 异步 HTTP 请求封装
    供各服务类继承
    """

    def __init__(self, ak: str, sk: str, region: str, project_id: Optional[str] = None):
        self.ak = ak
        self.sk = sk
        self.region = region
        self.project_id = project_id
        self.session = aiohttp.ClientSession()  # 可共享

    async def close(self):
        """关闭 aiohttp 会话"""
        await self.session.close()

    # -------------------------------
    # HTTP 请求封装
    # -------------------------------
    async def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Any] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        发送 HTTP 请求
        """
        headers = headers or {}

        async with self.session.request(
            method=method.upper(),
            url=url,
            headers=headers,
            json=body,
            timeout=timeout
        ) as resp:
            resp_json = await resp.json(content_type=None)
            if resp.status >= 400:
                raise RuntimeError(f"[HuaweiApiClient] {resp.status} {resp_json}")
            return resp_json

    # -------------------------------
    # 时间戳
    # -------------------------------
    @staticmethod
    def get_x_sdk_date() -> str:
        """返回 UTC 时间字符串 YYYYMMDDTHHMMSSZ"""
        return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    # -------------------------------
    # 签名（HMAC-SHA256）
    # -------------------------------
    def sign(self, string_to_sign: str) -> str:
        """
        用 SK 对 string_to_sign 计算 Signature
        """
        sk_bytes = self.sk.encode("utf-8")
        msg_bytes = string_to_sign.encode("utf-8")
        signature = hmac.new(sk_bytes, msg_bytes, hashlib.sha256).hexdigest()
        return signature

    # -------------------------------
    # 构造 Authorization Header
    # -------------------------------
    def build_authorization(
        self,
        signed_headers: str,
        signature: str
    ) -> str:
        """
        Authorization: SDK-HMAC-SHA256 Access=AKxxx, SignedHeaders=..., Signature=...
        """
        return f"SDK-HMAC-SHA256 Access={self.ak}, SignedHeaders={signed_headers}, Signature={signature}"

    # -------------------------------
    # URL 编码工具
    # -------------------------------
    @staticmethod
    def encode_uri(uri: str) -> str:
        """
        对 URI 进行 RFC3986 编码
        """
        return quote(uri, safe='/-_.~')

    # -------------------------------
    # 待子类实现的接口（抽象方法）
    # -------------------------------
    async def create_task(self, *args, **kwargs):
        raise NotImplementedError

    async def get_task_status(self, *args, **kwargs):
        raise NotImplementedError