import asyncio
import hashlib
import os
import time
from typing import List, Optional

from obs import ObsClient

from config.config import ENV, my_config
from exceptions.ServiceException import ServiceException
from utils.log_utils import logger as log
from utils.cache_utils import get_cached_path, set_cached_path

# === OBS 配置 ===
BUCKET_NAME = 'freeuuu'
OBS_BASE_URL = 'https://freeuuu.obs.cn-east-3.myhuaweicloud.com'
CDN_BASE_URL = "https://obs.freeuuu.com"
audio_output_dir = "../work"
obs_client = ObsClient(
    access_key_id=os.getenv("HUAWEI_OBS_AK", ""),
    secret_access_key=os.getenv("HUAWEI_OBS_SK", ""),
    server='obs.cn-east-3.myhuaweicloud.com'
)


async def upload_to_obs(filename: str, obs_prefix: str = "ai_picture/mark/demo/frames_test/", project_id=None) -> str:
    if project_id is not None:
        obs_prefix = obs_prefix + project_id
    fname = os.path.basename(filename)
    obs_key = os.path.join(obs_prefix, fname).replace("\\", "/")

    try:
        resp = await asyncio.to_thread(obs_client.putFile, bucketName=BUCKET_NAME, objectKey=obs_key,
                                       file_path=filename)
        if resp.status < 300:
            return f"{OBS_BASE_URL}/{obs_key}"
        else:
            raise ServiceException(code=461, message=f"obs上传异常，状态码{resp.status}")
    except Exception as e:
        raise ServiceException(code=457, message=f"obs上传异常，请检查{filename}文件是否存在", data=str(e))


def sha256_file(filename, chunk_size=512):
    m = hashlib.sha256()
    f = open(filename, 'rb')
    while True:
        b = f.read(chunk_size)
        if len(b) == 0:
            break
        m.update(b)
    return m.hexdigest()


async def download_from_obs(path, save_dir: str = "./obs_video") -> str:
    """
    从 OBS 下载文件并保存在本地指定目录，使用 diskcache 管理本地缓存。

    :param path: OBS 对象路径
    :param save_dir: 本地保存目录，默认 ./obs_video
    :return: 本地完整文件路径
    """
    filename = os.path.basename(path)
    local_path = os.path.join(save_dir, filename)
    fn, ext = os.path.splitext(filename)
    if not ext.lower() in [".mp4", ".mov", ".avi", ".wav", ".mp3", ".MP4", ".qt"]:
        raise ServiceException(code=461, message=f"{filename}文件不是合法格式")
    os.makedirs(save_dir, exist_ok=True)

    try:
        # 查询 diskcache 缓存（多进程安全，自带 TTL 续期）
        cached_path = await asyncio.to_thread(get_cached_path, path)
        if cached_path:
            return cached_path

        # 缓存未命中，从 OBS 下载
        start = time.time()
        log.info(f"{fn}开始下载")

        resp = await asyncio.to_thread(obs_client.getObject, bucketName=BUCKET_NAME, objectKey=path,
                                       downloadPath=local_path)
        d = time.time() - start

        log.info(f"{fn}下载任务执行了{d}秒")
        if resp.status < 300:
            log.debug(f"requestId: {resp.requestId}")
            log.info(f"{fn}下载成功")
            log.info(f"{local_path}:{sha256_file(local_path)}")

            # 写入 diskcache 缓存
            await asyncio.to_thread(set_cached_path, path, local_path)
            return local_path
        else:
            raise ServiceException(code=460, message=f"obs下载异常，状态码{resp.status}")
    except ServiceException:
        raise
    except Exception as e:
        raise ServiceException(code=440, message=f"obs下载异常，请检查{filename}文件是否存在", data=str(e))

async def batch_upload_to_obs(
    file_paths: List[str],
    obs_key_prefix: str,
    max_concurrency: int = 5,
) -> List[str]:
    sem = asyncio.Semaphore(max_concurrency)

    async def _upload(path: str):
        async with sem:
            file_name = os.path.basename(path)
            obs_key = f"{obs_key_prefix}/{file_name}"
            url = await upload_to_obs(path, obs_key)
            return url

    tasks = [_upload(p) for p in file_paths]
    obs_keys = await asyncio.gather(*tasks)

    return obs_keys

def obs_key_exists(obs_path: str) -> bool:
    """
    判断 OBS 对象是否存在

    Args:
        obs_path: obs 路径，如 obs://bucket/key 或 bucket/key
    Returns:
        True: 存在
        False: 不存在
    """


    try:
        key = obs_path

        resp = obs_client.headObject(BUCKET_NAME, key)

        # ✅ 核心判断点
        return resp.status < 300

    except Exception as e:

        log.exception(f"OBS 路径{obs_path}不存在 异常: {e}")
        return False



if __name__ == "__main__":
    # 手动测试用
    test_paths = [
        "aigc/aigc_local/1998/1998743094727520258/0/video/1765372463420.mp4",      # 换成一个你确定存在的 key
        "aigc/aigc_local/1998/1997943094727520258/0/video/1765372463421.mp4",  # 换成一个你确定不存在的 key
    ]

    for path in test_paths:
        exists = obs_key_exists(path)
        print(f"[TEST] obs_path={path}, exists={exists}")