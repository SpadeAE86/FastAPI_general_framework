import asyncio
import os
from typing import List

from utils.log_utils import logger as log
from config.config import my_config, RESOURCE_DIR, FINAL_DIR, ENV
from core.video_processing.sprite import generate_sprite, SpriteGenerateResult
from models.pydantic_models.request.sprite_image_request import SpriteImageRequest
from models.pydantic_models.response.sprite_image_response import SpriteImageResponse
from utils.ffmpeg_utils import extract_audio

from utils.general_utils import random_with_system_time, download_resource, get_video_info
from utils.obs_utils import upload_to_obs, batch_upload_to_obs


async def sprite_service(sprite_config: SpriteImageRequest) -> SpriteImageResponse:

    project_id = "sprite_" + str(random_with_system_time()) if not sprite_config.biz_id else "sprite_" + str(
        sprite_config.biz_id)  # 该次混剪资源所在的子文件夹名
    log.info(f"project_id: {project_id}")


    download_dir = None
    # 下载/vpc储存卷获取资源
    if my_config["direct_download"]:
        download_dir = f"{RESOURCE_DIR}/{project_id}"
        os.makedirs(download_dir, exist_ok=True)
    video_path_list: List[str] = await download_resource([sprite_config.obs_video_path], output_dir=download_dir)
    video_path = video_path_list[0]
    output_dir = f"{FINAL_DIR}/{project_id}"
    tasks = [
        asyncio.to_thread(generate_sprite,video_path, output_dir),
        asyncio.to_thread(extract_audio, video_path, project_id)
    ]
    sprite_result: SpriteGenerateResult
    audio_path: str
    sprite_result, audio_path = await asyncio.gather(*tasks)

    if not sprite_result:
        raise RuntimeError(f"生成雪碧图失败: task_id={project_id}")


    obs_key_prefix = f"aigc/aigc_{ENV}/{sprite_config.user_id}/sprite/{project_id}"
    upload_tasks = [
        batch_upload_to_obs(sprite_result.sprite_paths, obs_key_prefix),
        upload_to_obs(audio_path, obs_key_prefix) if audio_path else asyncio.sleep(0.1,result=""),
    ]

    sprite_url_list, audio_url = await asyncio.gather(*upload_tasks)
    resp: SpriteImageResponse = SpriteImageResponse(
        sprite_image_url_list=sprite_url_list,
        video_resolution_x=sprite_result.video_width,
        video_resolution_y=sprite_result.video_height,
        audio_url=audio_url,
        biz_id=sprite_config.biz_id
    )  # 业务逻辑

    return resp



async def my_test_sprite_service():
    req = SpriteImageRequest(
        obs_video_path="aigc/aigc_test/153/mix_125/final-1768470072480.mp4",  # 你稍后填
        biz_id=123
    )

    try:
        resp = await sprite_service(req)
    except Exception as e:
        print("❌ sprite_service 执行失败")
        raise

    print("✅ sprite_service 执行成功")
    print("返回结果：")
    print(f"biz_id: {resp.biz_id}")
    print(f"sprite_image_url_list: {resp.sprite_image_url_list}")
    print(f"audio_url: {resp.audio_url}")
    print(f"video_resolution: {resp.video_resolution_x} x {resp.video_resolution_y}")

if __name__ == "__main__":
    asyncio.run(my_test_sprite_service())