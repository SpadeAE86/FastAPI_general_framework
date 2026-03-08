# utils/huawei/mpc/mpc_async_client.py
import asyncio
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode
import time

import httpx
from utils.log_utils import logger as log
from models.pydantic_dataclass.transcode_output import TranscodeOutput, AudioStreamMeta, DynamicRangeInfo, \
    VideoStreamMeta
from utils.huawei.huawei_api_client import HuaweiApiClient
from utils.post_utils import get, DEFAULT_GET_TIMEOUT


class MpcAsyncClient(HuaweiApiClient):
    """
    MPC Async API Client（不使用官方 SDK）
    """
    # self.refresh_token

    def __init__(self):
        self.project_id = "610bebab20ea4e01b14a127b565a16c1"
        super().__init__(
            ak = os.getenv("HUAWEI_OBS_AK", ""),
            sk = os.getenv("HUAWEI_OBS_SK", ""),
            region = "cn-east-3",
            project_name=self.project_id
        )

    async def create_transcoding_task(
            self,
            input_bucket: str,
            input_object: str,
            output_bucket: str,
            output_object_prefix: str,
            template_ids: list[int],
            priority: int = 6,
            user_data: str | None = None
    ) -> Optional[str]:
        """
        创建转码任务（API版）
        """

        # 1. 确保 token 可用（建议你这里已经加了 asyncio.Lock）
        if self._token_expired():
            async with self._token_lock:
                if self._token_expired():
                    await self.refresh_token()

        url = f"https://mpc.{self.region}.myhuaweicloud.com/v1/{self.project_id}/transcodings"

        headers = {
            "X-Auth-Token": self._token,
            "Content-Type": "application/json"
        }

        body: Dict[str, Any] = {
            "input": {
                "bucket": input_bucket,
                "location": self.region,
                "object": input_object
            },
            "output": {
                "bucket": output_bucket,
                "location": self.region,
                "object": output_object_prefix
            },
            "trans_template_id": template_ids,
            "priority": priority
        }

        if user_data:
            body["user_data"] = user_data

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url,
                    headers=headers,
                    json=body,
                    timeout=DEFAULT_GET_TIMEOUT
                )

            if resp.status_code == 202:
                data = resp.json()
                task_id = data.get("task_id")
                log.info(f"创建转码任务成功 task_id={task_id}")
                return str(task_id)

            # 失败情况
            log.error(
                f"创建转码任务失败 status={resp.status_code}, body={resp.text}"
            )
            return None

        except httpx.TimeoutException:
            log.error("创建转码任务超时")
            return None
        except httpx.RequestError as e:
            log.error(f"创建转码任务请求异常: {e}")
            return None
        except Exception as e:
            log.exception(f"创建转码任务未知异常: {e}")
            return None


    async def get_transcoding_task_status(
        self,
        task_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        查询单个转码任务状态（async）
        对应：ListTranscodingTask
        """

        # 1. 确保 token 可用
        if self._token_expired():
            await self.refresh_token()

        url = f"https://mpc.{self.region}.myhuaweicloud.com/v1/{self.project_id}/transcodings"

        params = {
            "task_id": task_id
        }

        headers = {
            "X-Auth-Token": self._token
        }

        resp = await get(
            host=url,
            params=params,
            headers=headers,
            task_id=str(task_id)
        )

        if not resp:
            return None

        total = resp.get("total", 0)
        if total > 0:
            return resp["task_array"][0]

        return None

    async def wait_transcoding_success(
            self,
            task_id: int,
            poll_interval: int = 5,
            timeout: int = 600
    ) -> Optional[List[TranscodeOutput]]:

        start_time = time.time()

        while True:
            task_info = await self.get_transcoding_task_status(task_id)

            if task_info is None:
                raise ValueError(f"Task {task_id} 不存在或获取失败")

            status = task_info.get("status")

            if status == "SUCCEEDED":
                outputs = []

                multitask_info = task_info["transcode_detail"]["multitask_info"]
                output_file_names = task_info["output_file_name"]
                output_object = task_info["output"]["object"]

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
                            dynamic_range=DynamicRangeInfo(
                                type=v.get("dynamic_range")
                            )
                        )

                    if output_file.get("audio_info"):
                        a = output_file["audio_info"][0]
                        audio_meta = AudioStreamMeta(
                            codec=a.get("codec"),
                            sampling_rate=a.get("sample"),
                            bitrate=a.get("bitrate_bps")
                        )

                    file_name = output_file_names[idx]
                    obs_path = f"{output_object}/{file_name}"

                    outputs.append(
                        TranscodeOutput(
                            url=f"https://freeuuu.obs.{self.region}.myhuaweicloud.com/{obs_path}",
                            duration=output_file.get("duration"),
                            size=output_file.get("size", 0) * 1024,
                            width=video_meta.width if video_meta else None,
                            height=video_meta.height if video_meta else None,
                            video_meta=video_meta,
                            audio_meta=audio_meta
                        )
                    )

                return outputs

            elif status in ("FAILED", "CANCELED"):
                raise RuntimeError(f"Task {task_id} 执行失败，状态: {status}")

            else:
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Task {task_id} 超时")

                await asyncio.sleep(poll_interval)

if __name__ == "__main__":
    import asyncio

    async def main():
        client = MpcAsyncClient()

        # 第一次获取 token（自动刷新）
        print("第一次获取 token...")
        token1 = await client.refresh_token()
        print(f"token1: {token1}")

        # 再刷新 token
        print("刷新 token...")
        token2 = await client.refresh_token()
        print(f"token2: {token2}")

        # 验证是否刷新成功（理论上 token2 应该跟 token1 不同，或者值更新）
        print("再次获取 token（不强制刷新）...")
        if client._token_expired():
            token3 = await client.refresh_token()
        else:
            token3 = client._token
        print(f"token3: {token3}")

    asyncio.run(main())