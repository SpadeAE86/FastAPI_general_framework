import os
import time
import threading
from typing import Optional
from pathlib import Path

import diskcache
from diskcache import Disk
from utils.log_utils import logger as log

# --- 路径配置 ---
# 数据库存储目录（存放 SQLite 索引）
_DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "cache", "obs_db"))
# 物理文件存储目录（存放实际下载的文件）
_FILES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "cache", "obs_files"))

# 确保目录存在
os.makedirs(_DB_DIR, exist_ok=True)
os.makedirs(_FILES_DIR, exist_ok=True)

# 默认 TTL（秒）：10 分钟
DEFAULT_TTL = 600

# --- 自定义 Disk 逻辑 ---

class OBSFileDisk(Disk):
    """
    自定义磁盘管理插件
    当 diskcache 剔除一个 Key 时（过期或空间满），会自动调用 rem 方法。
    """
    def __init__(self, directory, **configs):
        # 这里的 directory 实际上是 cache 的数据库目录
        super().__init__(directory, **configs)

    def rem(self, value):
        """
        当条目被删除时自动删除物理文件
        """
        if value and isinstance(value, str) and os.path.exists(value):
            try:
                os.remove(value)
                log.info(f"[DiskCache] 物理文件已自动清理: {value}")
            except Exception as e:
                log.error(f"[DiskCache] 物理文件清理失败: {value}, error: {e}")

        super().rem(value)

# --- 初始化全局缓存 ---
# size_limit: 2GB (元数据+索引上限，不包含外部物理文件，但触发 LRU 时会清理物理文件)
cache = diskcache.Cache(
    _DB_DIR, 
    disk=OBSFileDisk, 
    size_limit=2 * (1024 ** 3)
)
log.info(f"[DiskCache] 初始化完成. DB: {_DB_DIR}, Files: {_FILES_DIR}")


# --- 业务 API ---

def get_cached_path(obs_key: str) -> Optional[str]:
    """
    获取缓存路径。
    如果命中：自动续期并返回路径。
    如果文件意外丢失：自动清理索引并返回 None。
    """
    local_path = cache.get(obs_key)

    if local_path is None:
        return None

    # 容错：如果数据库里有，但物理文件被手动删了
    if not os.path.exists(local_path):
        log.warning(f"[DiskCache] 索引存在但物理文件丢失，清理条目: {obs_key}")
        cache.delete(obs_key)
        return None

    # 命中续期：通过重新 set 触发新的过期时间
    cache.set(obs_key, local_path, expire=DEFAULT_TTL)
    log.debug(f"[DiskCache] 命中并续期: {obs_key}")
    return local_path


def set_cached_path(obs_key: str, local_path: str, ttl: int = DEFAULT_TTL) -> None:
    """
    存入缓存。
    local_path 建议放在 _FILES_DIR 目录下。
    """
    cache.set(obs_key, local_path, expire=ttl)
    log.info(f"[DiskCache] 写入缓存: {obs_key}, TTL={ttl}s")


def cleanup_expired_files() -> int:
    """
    主动触发过期检查。
    虽然 diskcache 在读写时会懒清理，但后台线程定期调用此方法
    可以确保在没有操作时也能及时释放磁盘空间。
    """
    try:
        # expire() 会遍历 SQLite 发现过期的 key，并对每个 key 调用 OBSFileDisk.rem()
        count = cache.expire()
        if count > 0:
            log.info(f"[DiskCache] 本轮后台清理完成，释放条目数: {count}")
        return count
    except Exception as e:
        log.error(f"[DiskCache] 执行 expire 异常: {e}", exc_info=True)
        return 0


# --- 后台线程 ---

def start_cleanup_thread(interval: int = 60) -> threading.Thread:
    """
    启动后台清理守护线程。
    """
    def _cleanup_loop():
        log.info(f"[DiskCache] 清理线程已启动，间隔: {interval}s")
        while True:
            cleanup_expired_files()
            time.sleep(interval)

    t = threading.Thread(
        target=_cleanup_loop,
        name="diskcache-auto-cleanup",
        daemon=True,
    )
    t.start()
    return t