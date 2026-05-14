# -*- coding: utf-8 -*-
"""
华为 MPC 转码试跑：对 OBS 上的源视频创建转码任务并轮询至成功。

环境变量（勿将真实密钥写入仓库）::

  HUAWEI_CLOUD_AK / HUAWEI_CLOUD_SK
  HUAWEI_REGION（默认 cn-east-3）
  HUAWEI_PROJECT_ID（控制台项目 ID，UUID）

  HUAWEI_MPC_OUTPUT_BUCKET     输出对象所在桶名（如与源相同可填源桶）
  HUAWEI_MPC_OUTPUT_PREFIX     输出对象前缀目录，如 mpc_out/test1
  HUAWEI_MPC_TEMPLATE_IDS      转码模板 ID 列表，逗号分隔，如 12345 或 123,456

Run::

  cd my_agent/src
  python -m test.transcode_obs_smoke

  python -m test.transcode_obs_smoke --url "https://freeuuu.obs.cn..." 

  请使用已安装本项目依赖的解释器（例如 Conda ``py312``），否则可能缺少 ``httpx``。
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import List, Tuple
from urllib.parse import unquote, urlparse

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(CURRENT_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from utils.huawei.mpc_async_client import mpc_client_from_env  # noqa: E402


def _parse_template_ids(raw: str) -> List[int]:
    parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    return [int(x) for x in parts]


def parse_obs_https_url(url: str) -> Tuple[str, str]:
    """
    解析 ``https://{bucket}.obs.{region}.myhuaweicloud.com/{object_key}``。
    返回 (bucket, object_key)；object_key 无前导斜杠。
    """
    u = urlparse(url.strip())
    if u.scheme not in ("http", "https") or not u.netloc:
        raise ValueError(f"invalid url: {url!r}")
    host_parts = u.netloc.lower().split(".")
    if len(host_parts) < 5 or host_parts[1] != "obs" or host_parts[4:5] != ["com"]:
        raise ValueError(f"not a Huawei OBS host: {u.netloc!r}")
    bucket = host_parts[0]
    key = unquote((u.path or "/").lstrip("/"))
    if not key:
        raise ValueError("empty object key")
    return bucket, key


async def main() -> None:
    parser = argparse.ArgumentParser(description="MPC transcode smoke (OBS source URL)")
    parser.add_argument(
        "--url",
        default=os.getenv(
            "TRANSCODE_SMOKE_URL",
            "https://freeuuu.obs.cn-east-3.myhuaweicloud.com/ai_picture/car_video_analysis/source_video/19ca2d690f0c59aa/20260513_111254_20260226-%E9%99%88%E9%BE%99-%E8%B7%AF%E8%B7%91-4.mp4",
        ),
        help="Source video HTTPS URL on Huawei OBS",
    )
    args = parser.parse_args()

    out_bucket = (os.getenv("HUAWEI_MPC_OUTPUT_BUCKET") or "").strip()
    out_prefix = (os.getenv("HUAWEI_MPC_OUTPUT_PREFIX") or "mpc_smoke_out").strip().strip("/")
    tid_raw = (os.getenv("HUAWEI_MPC_TEMPLATE_IDS") or "").strip()
    if not out_bucket:
        print("HUAWEI_MPC_OUTPUT_BUCKET is required", file=sys.stderr)
        sys.exit(2)
    if not tid_raw:
        print("HUAWEI_MPC_TEMPLATE_IDS is required (comma-separated integers)", file=sys.stderr)
        sys.exit(2)

    template_ids = _parse_template_ids(tid_raw)
    in_bucket, in_object = parse_obs_https_url(args.url)

    client = mpc_client_from_env()
    if client is None:
        print("mpc_client_from_env() failed; check HUAWEI_CLOUD_AK/SK and HUAWEI_PROJECT_ID", file=sys.stderr)
        sys.exit(2)

    print(f"input bucket={in_bucket} object={in_object}")
    print(f"output bucket={out_bucket} prefix={out_prefix}/ templates={template_ids}")

    task_id_str = await client.create_transcoding_task(
        input_bucket=in_bucket,
        input_object=in_object,
        output_bucket=out_bucket,
        output_object_prefix=out_prefix,
        template_ids=template_ids,
        priority=6,
    )
    if not task_id_str:
        print("create_transcoding_task returned None", file=sys.stderr)
        sys.exit(1)

    task_id = int(task_id_str)
    print(f"task_id={task_id}, polling...")
    outputs = await client.wait_transcoding_success(
        task_id,
        obs_bucket_for_url=out_bucket,
        poll_interval=5,
        timeout=900,
    )
    for i, o in enumerate(outputs):
        print(f"output[{i}] url={o.url} duration={o.duration} wxh={o.width}x{o.height}")


if __name__ == "__main__":
    asyncio.run(main())
