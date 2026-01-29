import asyncio
import hashlib
import os
import time
from typing import List, Optional

from obs import ObsClient

from config.config import ENV, VIDEO_CACHE_PREFIX, my_config
from exceptions.ServiceException import ServiceException
from utils.log_utils import logger as log
from utils.memory_utils import memory

from redis.asyncio import Redis
# === OBS 配置 ===
BUCKET_NAME = 'freeuuu'
OBS_BASE_URL = 'https://freeuuu.obs.cn-east-3.myhuaweicloud.com'
CDN_BASE_URL = "https://obs.freeuuu.com"
audio_output_dir = "../work"
obs_client = ObsClient(
    access_key_id='UJDPK31ANIBV0XTEUN5N',
    secret_access_key='NhQExxv9PUYsvmvGnVReizRksaiHcJdQ6vMMw19d',
    server='obs.cn-east-3.myhuaweicloud.com'
)

redis_client: Optional[Redis] = None
async def upload_to_obs(filename: str, obs_prefix: str = "ai_picture/mark/demo/frames_test/", project_id=None) -> str:
    if project_id is not None:
        obs_prefix = obs_prefix + project_id
    fname = os.path.basename(filename)
    obs_key = os.path.join(obs_prefix, fname).replace("\\", "/")

    try:
        resp = await asyncio.to_thread(obs_client.putFile, bucketName=BUCKET_NAME, objectKey=obs_key,
                                       file_path=filename)
        if resp.status < 300:
            return f"{CDN_BASE_URL}/{obs_key}"
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
    从 OBS 下载文件并保存在本地指定目录。

    :param filename: 要下载的文件名（不含路径）
    :param obs_prefix: OBS 上的前缀路径
    :param save_dir: 本地保存目录，默认当前目录
    :return: 本地完整文件路径
    """
    filename = os.path.basename(path)
    # 构造 OBS 中的对象 Key
    local_path = os.path.join(save_dir, filename)
    fn, ext = os.path.splitext(filename)
    if not ext.lower() in [".mp4", ".mov", ".avi", ".wav", ".mp3", ".MP4", ".qt"]:
        raise ServiceException(code=461, message=f"{filename}文件不是合法格式")
    # 确保保存目录存在
    os.makedirs(save_dir, exist_ok=True)

    # 下载文件
    try:
        ttl = 300  # 5 分钟
        cache_key = f"{VIDEO_CACHE_PREFIX}{path}"

        global redis_client

        if not redis_client:
            redis_client = Redis(host=my_config["redis"][ENV]["host"], port=my_config["redis"][ENV]["port"],
                                       password=my_config["redis"][ENV]["password"], decode_responses=True,
                                       db=my_config["redis"][ENV]["database"])  # 注意 host="redis"（服务名）
            log.info(f"redis client is not initialized, create new connection {redis_client}")
        local_path = await redis_client.get(cache_key)
        if local_path:
            log.info(f"[redis cache] path {path} exist, reuse download: {local_path}")
            log.info("[redis cache] refresh key...")
            await redis_client.expire(cache_key, ttl)  # 等价于 memory.touch
            return local_path

        start = time.time()
        log.info(f"{fn}开始下载")
        if path in memory:
            local_path = memory[path]
            log.info(f"path {path} exist, reuse download: {local_path}")  # 使用缓存
            log.info("refresh key...")
            memory.touch(path, local_path)
            return local_path

        resp = await asyncio.to_thread(obs_client.getObject, bucketName=BUCKET_NAME, objectKey=path,
                                       downloadPath=local_path)
        d = time.time() - start

        log.info(f"{fn}下载任务执行了{d}秒")
        if resp.status < 300:
            log.debug(f"requestId: {resp.requestId}")
            log.info(f"{fn}下载成功")
            log.info(f"{local_path}:{sha256_file(local_path)}")
            log.info(f"add to memory: {path} {local_path}")
            memory[path] = local_path  # 创建缓存
            await redis_client.setex(cache_key, ttl, local_path)
            log.info(f"[redis cache] add to redis: {cache_key} -> {local_path}")
            return local_path
        else:
            raise ServiceException(code=460, message=f"obs下载异常，状态码{resp.status}")
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
