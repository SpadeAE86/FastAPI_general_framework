from __future__ import annotations

import os
from typing import Tuple
from urllib.parse import unquote, urlparse


def parse_obs_https_url(url: str) -> Tuple[str, str]:
    """
    解析 ``https://{bucket}.obs.{region}.myhuaweicloud.com/{object_key}``。
    返回 (bucket, object_key)；object_key 无前导斜杠。
    """
    u = urlparse(url.strip())
    if u.scheme not in ("http", "https") or not u.netloc:
        raise ValueError(f"invalid url: {url!r}")
    host_parts = u.netloc.lower().split(".")
    if (
        len(host_parts) < 5
        or host_parts[1] != "obs"
        or host_parts[-2] != "myhuaweicloud"
        or host_parts[-1] != "com"
    ):
        raise ValueError(f"not a Huawei OBS host: {u.netloc!r}")
    bucket = host_parts[0]
    key = unquote((u.path or "/").lstrip("/"))
    if not key:
        raise ValueError("empty object key")
    return bucket, key


def mix_obs_object_path(url_or_path: str) -> str:
    """
    混剪 Worker 侧约定：``obs_*_path_list`` 为 **OBS 对象键**（无 scheme/域名）。
    若完整 URL 的路径中含 ``aigc/``，则从该处起截取（与现网素材前缀一致）；否则使用整段对象键。
    非华为 OBS 域名（如 CDN）时仅用 ``urlparse`` 取 path。
    """
    s = (url_or_path or "").strip()
    if not s:
        return ""
    key: str
    if s.startswith(("http://", "https://")):
        try:
            _, key = parse_obs_https_url(s)
        except ValueError:
            parsed = urlparse(s)
            key = unquote((parsed.path or "/").lstrip("/"))
    else:
        key = s.lstrip("/")

    key = key.strip()
    if not key:
        return ""
    idx = key.lower().find("aigc/")
    if idx >= 0:
        return key[idx:]
    return key


def transcode_output_prefix() -> str:
    return (os.getenv("HUAWEI_MPC_CACHE_TRANSCODE_PREFIX") or "mpc_transcode_cache").strip().strip("/")
