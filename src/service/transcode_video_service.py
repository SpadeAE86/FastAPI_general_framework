import asyncio
import json
import os
from models.pydantic_dataclass.transcode_output import TranscodeOutput, AudioStreamMeta, VideoStreamMeta, DynamicRangeInfo
from typing import List, Optional

from utils.log_utils import logger as log
from config.config import my_config, RESOURCE_DIR
from exceptions.ServiceException import ServiceException
from models.pydantic_models.request.mixed_video_request import MixedVideoRequest
from models.pydantic_models.request.transcode_video_request import TranscodeVideoRequest
from models.pydantic_models.response.transcode_video_response import TranscodeVideoResponse
from tencentcloud.vod.v20180717 import models
from utils.general_utils import random_with_system_time, download_resource
from utils.tencent.cos_uploader import vod_upload_to_cos
from utils.tencent.vod_uploader import TencentVodUploader

async def transcode_video_service(transcode_config: TranscodeVideoRequest):

    project_id = "transcode_" + str(random_with_system_time()) if not transcode_config.transcode_id else "transcode_" + str(
        transcode_config.transcode_id)  # 该次混剪资源所在的子文件夹名
    log.info(f"project_id: {project_id}")

    output_dir = None
    # 下载/vpc储存卷获取资源
    if my_config["direct_download"]:
        output_dir = f"{RESOURCE_DIR}/{project_id}"
        os.makedirs(output_dir, exist_ok=True)
    video_list = await download_resource([transcode_config.obs_video_path], output_dir=output_dir)
    video_path = video_list[0]
    tencent_vod_config = my_config.get("tencent", {}).get("vod", {})

    uploader = TencentVodUploader(
        secret_id=tencent_vod_config.get("secret_id"),
        secret_key=tencent_vod_config.get("secret_key"),
        sub_app_id=tencent_vod_config.get("sub_app_id")
    )

    # 1. 申请上传
    apply_resp = uploader.apply_upload(video_path=video_path, media_type="mp4")
    vod_session_key = apply_resp["VodSessionKey"]
    log.info(f"申请上传成功: task_id={project_id}, VodSessionKey={vod_session_key}")

    # 2. 上传到 COS
    vod_upload_to_cos(apply_resp, video_path)
    log.info(f"视频已上传到 COS: task_id={project_id}")

    low_resolution_template = 100010
    raw_resolution_template = 80000
    # 3. 提交上传并轮询结果
    transcode_result = uploader.commit_and_poll(vod_session_key)
    media_url = transcode_result.get("MediaUrl")
    file_id = transcode_result.get("FileId")
    log.info(f"视频上传确认成功: file_id={file_id}")

    if not media_url:
        raise RuntimeError(f"Transcode 完成但未返回 MediaUrl: task_id={project_id}")

    low_resolution_info: Optional[TranscodeOutput] = None
    raw_resolution_info: Optional[TranscodeOutput] = None
    transcode_set = []
    for i in range(10):
        media_info = uploader.describe_media_infos(
            file_id=file_id,
            filters=["transcodeInfo"]
        )

        transcode_info = media_info.get("TranscodeInfo", {})
        transcode_set = transcode_info.get("TranscodeSet", [])


        info_len = len(transcode_set)
        log.info(f"第{i}轮 返回长度: {info_len}")
        if info_len >= 3:
            break
        await asyncio.sleep(4)


    if len(transcode_set) < 3:
        raise ServiceException(message = f"transcode fail", code = 100001)

    for item in transcode_set:
        log.info(f"[element]: {item}")
        definition = item.get("Definition")

        if definition == low_resolution_template:
            low_resolution_info = parse_transcode_set(item)
            log.info(f"#low_resolution_info: {low_resolution_info}")
        elif definition == raw_resolution_template:
            raw_resolution_info = parse_transcode_set(item)
            log.info(f"#raw_resolution_info: {raw_resolution_info}")

    log.info(f"转码完成: task_id={project_id}, raw_resolution_video_url={media_url}")
    resp: TranscodeVideoResponse = TranscodeVideoResponse(
        low_resolution_video_url=low_resolution_info.url,
        low_resolution_video_meta=low_resolution_info,
        raw_resolution_video_url=raw_resolution_info.url,
        raw_resolution_video_meta=raw_resolution_info,
        transcode_id=123
    )  # 业务逻辑

    return resp


def parse_transcode_set(transcode_result) -> TranscodeOutput:

    log.info(f"[parse_transcode_set] | transcode result: {transcode_result}")
    video_stream = transcode_result.get("VideoStreamSet", [])
    audio_stream = transcode_result.get("AudioStreamSet", [])

    video_meta: Optional[VideoStreamMeta] = None

    if video_stream:
        v = video_stream[0]
        dyn = v.get("DynamicRangeInfo", {})

        dynamic_range = DynamicRangeInfo(
            type=dyn.get("Type"),
            hdr_type=dyn.get("HDRType") or None
        )

        fps_raw = v.get("Fps")
        fps = fps_raw / 100 if fps_raw else None

        video_meta = VideoStreamMeta(
            codec=v.get("Codec"),
            width=v.get("Width"),
            height=v.get("Height"),
            fps=fps,
            bitrate=v.get("Bitrate"),
            dynamic_range=dynamic_range,
            size=transcode_result.get("Size"),
        )

    # -------- Audio Meta --------
    audio_meta: Optional[AudioStreamMeta] = None

    if audio_stream:
        a = audio_stream[0]
        audio_meta = AudioStreamMeta(
            codec=a.get("Codec"),
            sampling_rate=a.get("SamplingRate"),
            bitrate=a.get("Bitrate")
        )

    return TranscodeOutput(
        url=transcode_result.get("Url"),
        duration=transcode_result.get("Duration"),
        width=transcode_result.get("Width"),
        height=transcode_result.get("Height"),
        video_meta=video_meta,
        audio_meta=audio_meta
    )

async def my_test_transcode_video_service():
    req = TranscodeVideoRequest(
        obs_video_path="aigc/aigc_prod/1447/1999061725840629762/0/video/1765448404442.mp4",  # 替换为真实可用路径
        transcode_id=123,
    )

    try:
        resp = await transcode_video_service(req)
    except Exception as e:
        print("❌ transcode_video_service 执行失败")
        raise

    print("✅ transcode_video_service 执行成功")
    print("返回结果：")
    print(f"transcode_id: {resp.transcode_id}")
    print(f"low_resolution_video_url: {resp.low_resolution_video_url}")
    print(f"raw_resolution_video_url: {resp.raw_resolution_video_url}")


if __name__ == "__main__":
    asyncio.run(my_test_transcode_video_service())