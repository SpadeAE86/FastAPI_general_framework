from __future__ import annotations

import os
import time
import asyncio
from typing import Optional

import httpx

from infra.logging.logger import logger as log


class HuaweiIamAkSkClient:
    """
    华为云 IAM v3：使用 AK/SK 获取 X-Subject-Token（不使用账号密码）。
    环境变量：HUAWEI_CLOUD_AK、HUAWEI_CLOUD_SK、HUAWEI_REGION、HUAWEI_PROJECT_ID（项目 ID，UUID）。
    """

    def __init__(
        self,
        *,
        ak: str,
        sk: str,
        region: str,
        project_id: str,
    ):
        self.ak = ak.strip()
        self.sk = sk.strip()
        self.region = (region or "cn-east-3").strip()
        self.project_id = project_id.strip()
        self._token: Optional[str] = None
        self._token_expire_at: float = 0.0
        self._token_lock = asyncio.Lock()

    @classmethod
    def from_env(cls) -> Optional[HuaweiIamAkSkClient]:
        ak = os.getenv("HUAWEI_AK", "").strip()
        sk = os.getenv("HUAWEI_SK", "").strip()
        region = os.getenv("HUAWEI_REGION", "cn-east-3").strip()
        pid = os.getenv("HUAWEI_PROJECT_ID", "").strip()
        if not ak or not sk or not pid:
            log.warning("HuaweiIamAkSkClient.from_env: missing HUAWEI_AK/SK or HUAWEI_PROJECT_ID")
            return None
        return cls(ak=ak, sk=sk, region=region, project_id=pid)

    def _token_expired(self) -> bool:
        return not self._token or time.time() > self._token_expire_at - 120.0

    async def refresh_token(self) -> str:
        """获取或刷新 Token。"""
        url = f"https://iam.{self.region}.myhuaweicloud.com/v3/auth/tokens"
        payload = {
            "auth": {
                "identity": {
                    "methods": ["hw_ak_sk"],
                    "hw_ak_sk": {
                        "access": {"key": self.ak},
                        "secret": {"key": self.sk},
                    },
                },
                "scope": {
                    "project": {
                        "id": self.project_id,
                    }
                },
            }
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code not in (200, 201):
            text = resp.text[:2000]
            raise RuntimeError(f"IAM token failed: {resp.status_code} {text}")

        token = resp.headers.get("X-Subject-Token")
        if not token:
            raise RuntimeError("IAM response missing X-Subject-Token header")

        self._token = token
        self._token_expire_at = time.time() + 20 * 3600
        return token

    async def get_token(self) -> str:
        if not self._token_expired():
            assert self._token is not None
            return self._token
        async with self._token_lock:
            if not self._token_expired():
                assert self._token is not None
                return self._token
            return await self.refresh_token()
