# utils/huawei/core/huawei_api_client.py
import asyncio
import time
import hmac
import hashlib
import base64
import aiohttp
from typing import Optional, Dict, Any
from urllib.parse import urlparse, quote
import httpx
from utils.log_utils import logger as log
from huaweicloudsdkmpc.v1 import MpcClient


class HuaweiApiClient:
    def __init__(self, ak: str, sk: str, region: str, project_name: str):
        self.ak = ak
        self.sk = sk
        self.region = region
        self.project_name = project_name

        # Token 相关
        self._token: Optional[str] = None
        self._token_expire_at: float = 0.0  # unix timestamp
        # 初始化 asyncio.Lock，用于 token 刷新时保证互斥
        self._token_lock = asyncio.Lock()


    def _token_expired(self) -> bool:
        return not self._token or time.time() > self._token_expire_at - 60  # 提前 1 分钟刷新

    async def refresh_token(self) -> str:
        """
        使用 AK/SK 获取 IAM Token（httpx 版本）
        Token 有效期：内部固定 20 小时
        """
        url = f"https://iam.{self.region}.myhuaweicloud.com/v3/auth/tokens"

        payload = {
            "auth": {
                "identity": {
                    "methods": ["password"],
                    "password": {
                        "user": {
                            "name": "linnuocheng",
                            "password": "APTX-4869a",
                            "domain": {"name": "mpn199"}
                        }
                    }
                },
                "scope": {
                    "project": {
                        "name": self.project_name
                    }
                }
            }
        }
        log.info(f"pay load: {payload}")
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
            except httpx.RequestError as e:
                raise RuntimeError(f"[HuaweiApiClient] token request failed: {e}")
            except httpx.HTTPStatusError:
                text = resp.text
                raise RuntimeError(f"[HuaweiApiClient] get token failed: {resp.status_code} {text}")

        token = resp.headers.get("X-Subject-Token")
        if not token:
            raise RuntimeError("[HuaweiApiClient] X-Subject-Token not found in response headers")

        self._token = token
        self._token_expire_at = time.time() + 20 * 60 * 60  # 20 小时

        return token
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

# if __name__ == "__main__":
#     lient = MpcClient.new_builder() \
#         .with_credentials(credentials) \
#         .with_region(MpcRegion.value_of(region)) \
#         .build()