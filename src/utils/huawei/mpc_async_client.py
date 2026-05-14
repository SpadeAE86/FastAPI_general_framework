from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

import httpx

from infra.logging.logger import logger as log
from models.pydantic.dataclass.transcode_output import (
    AudioStreamMeta,
    DynamicRangeInfo,
    TranscodeOutput,
    VideoStreamMeta,
)
from utils.huawei.huawei_iam_client import HuaweiIamAkSkClient
from utils.post_utils import DEFAULT_GET_TIMEOUT, get


class MpcAsyncClient:
    """
    华为云 MPC 媒体处理异步转码 API（REST，非官方 SDK）。
    需配合 ``HuaweiIamAkSkClient`` 获取的 Token。
    """

    def __init__(self, iam: HuaweiIamAkSkClient):
        self._iam = iam
        self.region = iam.region
        self.project_id = iam.project_id

    async def create_transcoding_task(
        self,
        *,
        input_bucket: str,
        input_object: str,
        output_bucket: str,
        output_object_prefix: str,
        template_ids: List[int],
        priority: int = 6,
        user_data: Optional[str] = None,
    ) -> Optional[str]:
        token = await self._iam.get_token()
        url = f"https://mpc.{self.region}.myhuaweicloud.com/v1/{self.project_id}/transcodings"
        headers = {
            "X-Auth-Token": token,
            "Content-Type": "application/json",
        }
        body: Dict[str, Any] = {
            "input": {
                "bucket": input_bucket.strip(),
                "location": self.region,
                "object": input_object.lstrip("/"),
            },
            "output": {
                "bucket": output_bucket.strip(),
                "location": self.region,
                "object": output_object_prefix.rstrip("/") + "/",
            },
            "trans_template_id": [int(x) for x in template_ids],
            "priority": priority,
        }
        if user_data:
            body["user_data"] = user_data

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, headers=headers, json=body, timeout=DEFAULT_GET_TIMEOUT)
            if resp.status_code == 202:
                data = resp.json()
                task_id = data.get("task_id")
                log.info("MPC create_transcoding_task ok task_id=%s", task_id)
                return str(task_id) if task_id is not None else None
            log.error("MPC create failed status=%s body=%s", resp.status_code, resp.text[:2000])
            return None
        except httpx.TimeoutException:
            log.error("MPC create_transcoding_task timeout")
            return None
        except httpx.RequestError as e:
            log.error("MPC create_transcoding_task request error: %s", e)
            return None

    async def get_transcoding_task_status(self, task_id: int) -> Optional[Dict[str, Any]]:
        token = await self._iam.get_token()
        url = f"https://mpc.{self.region}.myhuaweicloud.com/v1/{self.project_id}/transcodings"
        params = {"task_id": task_id}
        headers = {"X-Auth-Token": token}
        resp = await get(host=url, params=params, headers=headers, task_id=str(task_id))
        if not resp:
            return None
        total = resp.get("total", 0)
        if total > 0 and resp.get("task_array"):
            return resp["task_array"][0]
        return None

    async def wait_transcoding_success(
        self,
        task_id: int,
        *,
        obs_bucket_for_url: str,
        poll_interval: int = 5,
        timeout: int = 600,
    ) -> List[TranscodeOutput]:
        start_time = time.time()
        while True:
            task_info = await self.get_transcoding_task_status(task_id)
            if task_info is None:
                raise ValueError(f"MPC task {task_id} not found or query failed")
            status = task_info.get("status")
            if status == "SUCCEEDED":
                outputs: List[TranscodeOutput] = []
                multitask_info = task_info["transcode_detail"]["multitask_info"]
                output_file_names = task_info["output_file_name"]
                output_object = task_info["output"]["object"]
                bkt = obs_bucket_for_url.strip()
                for idx, multi in enumerate(multitask_info):
                    output_file = multi["output_file"]
                    video_meta = None
                    audio_meta = None
                    if output_file.get("video_info"):
                        v = output_file["video_info"]
                        video_meta = VideoStreamMeta(
                            codec=v.get("codec"),
                            width=v.get("width"),
                            height=v.get("height"),
                            fps=v.get("frame_rate"),
                            bitrate=v.get("bitrate_bps"),
                            dynamic_range=DynamicRangeInfo(type=v.get("dynamic_range")),
                        )
                    if output_file.get("audio_info"):
                        a = output_file["audio_info"][0]
                        audio_meta = AudioStreamMeta(
                            codec=a.get("codec"),
                            sampling_rate=a.get("sample"),
                            bitrate=a.get("bitrate_bps"),
                        )
                    file_name = output_file_names[idx]
                    obs_path = f"{output_object.rstrip('/')}/{file_name}".lstrip("/")
                    url = f"https://{bkt}.obs.{self.region}.myhuaweicloud.com/{obs_path}"
                    outputs.append(
                        TranscodeOutput(
                            url=url,
                            duration=output_file.get("duration"),
                            size=int(output_file.get("size", 0) * 1024) if output_file.get("size") else None,
                            width=video_meta.width if video_meta else None,
                            height=video_meta.height if video_meta else None,
                            video_meta=video_meta,
                            audio_meta=audio_meta,
                        )
                    )
                return outputs
            if status in ("FAILED", "CANCELED"):
                raise RuntimeError(f"MPC task {task_id} failed status={status}")
            if time.time() - start_time > timeout:
                raise TimeoutError(f"MPC task {task_id} poll timeout")
            await asyncio.sleep(poll_interval)


def mpc_client_from_env() -> Optional[MpcAsyncClient]:
    iam = HuaweiIamAkSkClient.from_env()
    if iam is None:
        return None
    return MpcAsyncClient(iam)
