import asyncio
import os
from typing import Optional

from utils.log_utils import logger as log
from config.config import my_config, ENV
from exceptions.ServiceException import ServiceException

from models.pydantic_models.request.transcode_video_request import TranscodeVideoRequest
from models.pydantic_models.response.transcode_video_response import TranscodeVideoResponse
from models.pydantic_dataclass.transcode_output import TranscodeOutput

from utils.general_utils import random_with_system_time
from utils.huawei.mpc_manager import HuaweiMPCClient


async def transcode_video_service_v2(
    transcode_config: TranscodeVideoRequest
) -> TranscodeVideoResponse:
    """
    华为云 MPC 转码服务（v2）
    """

    # -----------------------------
    # 0. 基础信息
    # -----------------------------
    project_id = (
        f"transcode_{random_with_system_time()}"
        if not transcode_config.biz_id
        else f"transcode_{transcode_config.biz_id}"
    )
    log.info(f"[MPC] project_id={project_id}")

    input_bucket, input_object = "freeuuu", transcode_config.obs_video_path

    output_bucket = "freeuuu"
    output_prefix = f"aigc/aigc_{ENV}/{transcode_config.user_id}/{project_id}/"


    template_ids = [
        21117,
        21118
    ]

    client = HuaweiMPCClient()

    # -----------------------------
    # 1. 创建转码任务
    # -----------------------------
    task_id = client.create_transcoding_task(
        input_bucket=input_bucket,
        input_object=input_object,
        output_bucket=output_bucket,
        output_object_prefix=output_prefix,
        template_ids=template_ids
    )

    if not task_id:
        raise ServiceException(message="创建转码任务失败", code=100001)

    log.info(f"[MPC] 创建转码任务成功 task_id={task_id}")

    # -----------------------------
    # 2. 等待转码完成
    # -----------------------------
    outputs: list[TranscodeOutput] = await client.wait_transcoding_success(
        task_id=int(task_id),
        poll_interval=5,
        timeout=600
    )

    if not outputs or len(outputs) < 2:
        raise ServiceException(message="转码结果不足", code=100002)

    # -----------------------------
    # 3. 区分清晰度
    # -----------------------------
    low_resolution_info: Optional[TranscodeOutput] = None
    raw_resolution_info: Optional[TranscodeOutput] = None

    resolutions = sorted(outputs, key=lambda o: o.video_meta.width)
    log.info(f"[MPC][output]{low_resolution_info}, {raw_resolution_info}")

    low_resolution_info = resolutions[0]
    raw_resolution_info = resolutions[-1]

    if not low_resolution_info or not raw_resolution_info:
        raise ServiceException(message="无法识别转码清晰度结果", code=100003)

    # -----------------------------
    # 4. 截图（同步）
    # -----------------------------
    cover_image_url = client.create_thumbnail_sync(
        input_bucket=input_bucket,
        input_object=input_object,
        output_bucket=output_bucket,
        output_object_prefix=f"{output_prefix}/cover",
        thumbnail_time_ms=0,
        short_edge=360
    )

    if not cover_image_url:
        log.warning("[MPC] 封面截图失败")
        cover_image_url = ""

    # -----------------------------
    # 5. 返回结果
    # -----------------------------
    resp = TranscodeVideoResponse(
        low_resolution_video_url=low_resolution_info.url,
        low_resolution_video_meta=low_resolution_info,
        raw_resolution_video_url=raw_resolution_info.url,
        raw_resolution_video_meta=raw_resolution_info,
        cover_image=rf"https://freeuuu.obs.cn-east-3.myhuaweicloud.com/{cover_image_url}",
        biz_id=transcode_config.biz_id
    )

    log.info(
        f"[MPC] 转码完成 "
        f"low={low_resolution_info.url} "
        f"raw={raw_resolution_info.url} "
        f"cover={cover_image_url}"
    )

    return resp

async def my_test_transcode_video_service_v2():
    req = TranscodeVideoRequest(
        obs_video_path="aigc/aigc_prod/1447/1999061725840629762/0/video/1765448404442.mp4",
        biz_id=123,
    )

    try:
        resp = await transcode_video_service_v2(req)
    except Exception as e:
        print("❌ transcode_video_service_v2 执行失败")
        raise

    print("✅ transcode_video_service_v2 执行成功")
    print("返回结果：")
    print(f"biz_id: {resp.biz_id}")
    print(f"cover_image: {resp.cover_image}")

    print(f"low_resolution_video_url: {resp.low_resolution_video_url}")
    print(f"low_resolution_video_meta: {resp.low_resolution_video_meta}")

    print(f"raw_resolution_video_url: {resp.raw_resolution_video_url}")
    print(f"raw_resolution_video_meta: {resp.raw_resolution_video_meta}")


if __name__ == "__main__":
    asyncio.run(my_test_transcode_video_service_v2())