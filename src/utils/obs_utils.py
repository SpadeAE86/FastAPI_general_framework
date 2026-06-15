import asyncio
import hashlib
import os
import time
from typing import List, Optional

from obs import ObsClient

from config.config import ENV, my_config
from exceptions.ServiceException import ServiceException
from utils.log_utils import logger as log
from utils.cache_utils import get_from_cache, set_to_cache

# === OBS / COS 配置 ===
def is_tencent():
    return my_config.get("platform") == "tencent"

# Load the active platform's object storage configuration
storage_config = my_config.get("object_storage", {})
BUCKET_NAME = storage_config.get("bucket", "freeuuu")
REGION = storage_config.get("region", "cn-east-3")

OBS_BASE_URL = f"https://{BUCKET_NAME}.obs.{REGION}.myhuaweicloud.com"
CDN_BASE_URL = "https://obs.freeuuu.com"
audio_output_dir = "../work"

obs_client = ObsClient(
    access_key_id=os.getenv("OBS_ACCESS_KEY_ID") or 'UJDPK31ANIBV0XTEUN5N',
    secret_access_key=os.getenv("OBS_SECRET_ACCESS_KEY") or 'NhQExxv9PUYsvmvGnVReizRksaiHcJdQ6vMMw19d',
    server=f"obs.{REGION}.myhuaweicloud.com"
)

TENCENT_SECRET_ID = os.getenv("TENCENT_SECRET_ID") or my_config.get("tencent", {}).get("vod", {}).get("secret_id")
TENCENT_SECRET_KEY = os.getenv("TENCENT_SECRET_KEY") or my_config.get("tencent", {}).get("vod", {}).get("secret_key")
TENCENT_APPID = os.getenv("TENCENT_APPID") or my_config.get("tencent", {}).get("vod", {}).get("sub_app_id")
TENCENT_BUCKET = BUCKET_NAME
TENCENT_REGION = REGION

cos_client = None
if is_tencent():
    try:
        from qcloud_cos import CosConfig, CosS3Client
        cos_config = CosConfig(
            Region=TENCENT_REGION,
            SecretId=TENCENT_SECRET_ID,
            SecretKey=TENCENT_SECRET_KEY,
            Scheme="https"
        )
        cos_client = CosS3Client(cos_config)
    except Exception as e:
        log.exception(f"Failed to initialize Tencent COS client: {e}")

obs_audio_prefix = f"aigc/aigc_{my_config['env']}/"

def get_key_from_url(url_or_key: str) -> str:
    if url_or_key.startswith("http://") or url_or_key.startswith("https://"):
        from urllib.parse import urlparse
        parsed = urlparse(url_or_key)
        return parsed.path.lstrip('/')
    return url_or_key

async def upload_audio(audio_path, project_id="test"):
    print(f"开始上传音频{audio_path}")
    if not audio_path:
        return ""
    obs_audio_path = await upload_to_obs(audio_path, obs_audio_prefix, project_id)
    obs_audio_path = obs_audio_path.replace("\\", "/")
    return obs_audio_path

async def upload_to_obs(filename: str, obs_prefix: str = "ai_picture/mark/demo/frames_test/", project_id=None) -> str:
    if project_id is not None:
        obs_prefix = obs_prefix + project_id
    fname = os.path.basename(filename)
    obs_key = os.path.join(obs_prefix, fname).replace("\\", "/")

    if is_tencent():
        try:
            await asyncio.to_thread(
                cos_client.upload_file,
                Bucket=TENCENT_BUCKET,
                Key=obs_key,
                LocalFilePath=filename,
                EnableMD5=False
            )
            return f"https://{TENCENT_BUCKET}.cos.{TENCENT_REGION}.myqcloud.com/{obs_key}"
        except Exception as e:
            raise ServiceException(code=457, message=f"cos上传异常，请检查{filename}文件是否存在", data=str(e))
    else:
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
    从 OBS / COS 下载文件并保存在本地指定目录，使用 diskcache 管理本地缓存。
    """
    import uuid
    filename = os.path.basename(path)
    # 给每次下载分配独立的临时文件名，防止同时并发下载时造成文件读写冲突崩溃
    temp_local_name = f"{uuid.uuid4().hex}_{filename}"
    local_path = os.path.join(save_dir, temp_local_name)
    fn, ext = os.path.splitext(filename)
    if not ext.lower() in [".mp4", ".mov", ".avi", ".wav", ".mp3", ".MP4", ".qt"]:
        raise ServiceException(code=461, message=f"{filename}文件不是合法格式")
    os.makedirs(save_dir, exist_ok=True)

    key = get_key_from_url(path)

    try:
        # 查询 diskcache 缓存（多进程安全，自带 TTL 续期）
        cached_path = await asyncio.to_thread(get_from_cache, path, True)
        if cached_path:
            return str(cached_path)

        # 缓存未命中，从 OBS / COS 下载
        start = time.time()
        log.info(f"{fn}开始下载")

        if is_tencent():
            await asyncio.to_thread(
                cos_client.download_file,
                Bucket=TENCENT_BUCKET,
                Key=key,
                DestFilePath=local_path
            )
            download_success = True
        else:
            resp = await asyncio.to_thread(obs_client.getObject, bucketName=BUCKET_NAME, objectKey=key,
                                           downloadPath=local_path)
            download_success = resp.status < 300
            if not download_success:
                raise ServiceException(code=460, message=f"obs下载异常，状态码{resp.status}，文件路径: {path}")

        d = time.time() - start

        log.info(f"{fn}下载任务执行了{d}秒")
        if download_success:
            log.info(f"{fn}下载成功")
            log.info(f"{local_path}:{sha256_file(local_path)}")

            # 写入 diskcache 缓存
            def write_cache_and_clean():
                with open(local_path, 'rb') as f:
                    set_to_cache(path, f)
                
                # 删除临时下载的文件，释放磁盘空间
                try:
                    os.remove(local_path)
                except Exception as cleanup_err:
                    log.warning(f"Failed to delete temp file {local_path}: {cleanup_err}")

                return get_from_cache(path, as_path=True)
            
            final_cached_path = await asyncio.to_thread(write_cache_and_clean)
            return str(final_cached_path) if final_cached_path else local_path
        else:
            raise ServiceException(code=460, message=f"下载异常，文件路径: {path}")
    except ServiceException:
        raise
    except Exception as e:
        raise ServiceException(code=440, message=f"下载异常，请检查{filename}文件是否存在", data=str(e))

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
    判断 OBS / COS 对象是否存在
    """
    key = get_key_from_url(obs_path)
    try:
        if is_tencent():
            cos_client.head_object(Bucket=TENCENT_BUCKET, Key=key)
            return True
        else:
            resp = obs_client.headObject(BUCKET_NAME, key)
            return resp.status < 300
    except Exception as e:
        log.info(f"对象路径{obs_path}不存在: {e}")
        return False

if __name__ == "__main__":
    # 手动测试用
    test_paths = [
        "aigc/aigc_local/1998/1998743094727520258/0/video/1765372463420.mp4",
        "aigc/aigc_local/1998/1997943094727520258/0/video/1765372463421.mp4",
    ]
    for path in test_paths:
        exists = obs_key_exists(path)
        print(f"[TEST] obs_path={path}, exists={exists}")