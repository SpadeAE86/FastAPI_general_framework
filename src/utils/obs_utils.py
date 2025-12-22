import asyncio, hashlib
from cachetools import TTLCache
from obs import ObsClient
from exceptions.ServiceException import ServiceException
import os, time, threading
from config.config import my_config
from utils.log_utils import logger as log


async def on_evict(key, value):
    if os.path.exists(value):
        value = value.replace("\\", "/")
        if os.path.exists(value):
            os.remove(value)
            log.info(f"[Evicted]: {key} {value}")


class CleanupTTLCache(TTLCache):
    def __init__(self, maxsize, ttl, on_evicted=None):
        super().__init__(maxsize, ttl)
        self.on_evicted = on_evicted  # 自定义的清理回调函数
        self._lock = threading.Lock()
        self.refresh = {}

    def expire(self, time=None):
        expired_items = super().expire(time)
        # 添加 None 检查和非空检查
        if expired_items is None:
            return expired_items
        for key, value in expired_items:
            if key not in self.refresh and my_config["env"] == "local":
                try:
                    self.loop.create_task(self.on_evicted(key, value))
                except Exception as e:
                    log.info(f"[CleanupTTLCache] Error during eviction callback: {e}")
        return expired_items

    def inject_fastapi_loop(self, loop):
        self.loop = loop

    def touch(self, key, value):
        print(f"[Touch] Thread {threading.get_ident()} WAITING for lock...")  # 调试
        with self._lock:
            log.info(f"[Touch] Thread {threading.get_ident()} GET lock")
            self.refresh[key] = True
            if key in self:
                del self[key]
                self[key] = value  # 刷新缓存
            del self.refresh[key]
        log.info(f"[Touch] Thread {threading.get_ident()} RELEASED lock")

    def load_memory(self, data):
        for key, value in data.items():
            self[key] = value
            log.info(f"insert memory {key}: {value}")



memory = CleanupTTLCache(maxsize=100, ttl=1000, on_evicted=on_evict)  # 缓存管理
# === OBS 配置 ===
BUCKET_NAME = 'freeuuu'
OBS_BASE_URL = 'https://freeuuu.obs.cn-east-3.myhuaweicloud.com'
audio_output_dir = "../work"
obs_client = ObsClient(
    access_key_id='UJDPK31ANIBV0XTEUN5N',
    secret_access_key='NhQExxv9PUYsvmvGnVReizRksaiHcJdQ6vMMw19d',
    server='obs.cn-east-3.myhuaweicloud.com'
)


async def upload_to_obs(filename: str, obs_prefix: str = "ai_picture/mark/demo/frames_test/", user=None) -> str:
    if user is not None:
        obs_prefix = obs_prefix + user
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
        if path in memory:
            local_path = memory[path]
            log.info(f"path {path} exist, reuse download: {local_path}")  # 使用缓存
            log.info("refresh key...")
            memory.touch(path, local_path)
            return local_path
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
            log.info(f"add to memory: {path} {local_path}")
            memory[path] = local_path  # 创建缓存
            return local_path
        else:
            raise ServiceException(code=460, message=f"obs下载异常，状态码{resp.status}")
    except Exception as e:
        raise ServiceException(code=440, message=f"obs下载异常，请检查{filename}文件是否存在", data=str(e))
