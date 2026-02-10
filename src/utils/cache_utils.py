"""
OBS 文件下载缓存管理 (基于 diskcache)

使用 diskcache (SQLite-backed) 替代 Redis shadow key 模式，
提供多进程安全的本地文件缓存管理。

特性：
- 多进程/多 worker 安全（SQLite WAL 模式）
- 自带 TTL 过期
- 过期后自动清理本地文件（通过后台线程）
"""
import os
import time
import threading
from typing import Optional

import diskcache

from utils.log_utils import logger as log

# 缓存目录：项目根目录下的 cache/obs_files
_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "cache", "obs_files")
_CACHE_DIR = os.path.abspath(_CACHE_DIR)

# 默认 TTL（秒）
DEFAULT_TTL = 600

# diskcache 全局实例（多进程安全）
cache = diskcache.Cache(_CACHE_DIR, size_limit=2 * (1024 ** 3))  # 2GB 元数据上限

log.info(f"[DiskCache] 初始化缓存目录: {_CACHE_DIR}")


def get_cached_path(obs_key: str) -> Optional[str]:
    """
    查询缓存中 obs_key 对应的本地文件路径。

    如果命中且本地文件仍存在，则续期并返回路径；
    否则返回 None（过期或文件已被删除）。

    Args:
        obs_key: OBS 对象路径

    Returns:
        本地文件路径，或 None
    """
    local_path = cache.get(obs_key)

    if local_path is None:
        return None

    # 文件已被外部删除，清理缓存条目
    if not os.path.exists(local_path):
        log.warning(f"[DiskCache] 缓存命中但文件不存在，清理条目: {obs_key} -> {local_path}")
        cache.delete(obs_key)
        return None

    # 命中：续期（重新写入以刷新 TTL）
    cache.set(obs_key, local_path, expire=DEFAULT_TTL)
    log.info(f"[DiskCache] 缓存命中并续期: {obs_key} -> {local_path}")
    return local_path


def set_cached_path(obs_key: str, local_path: str, ttl: int = DEFAULT_TTL) -> None:
    """
    写入缓存条目。

    Args:
        obs_key: OBS 对象路径
        local_path: 本地文件路径
        ttl: 过期时间（秒），默认 600
    """
    cache.set(obs_key, local_path, expire=ttl)
    log.info(f"[DiskCache] 写入缓存: {obs_key} -> {local_path}, TTL={ttl}s")


def cleanup_expired_files() -> int:
    """
    清理过期缓存条目对应的本地文件。

    diskcache 过期后条目仍保留在 SQLite 中直到被主动清理。
    此函数遍历已过期但未清理的条目，删除对应的本地文件。

    Returns:
        清理的文件数量
    """
    cleaned = 0

    # expire() 会从内部 SQLite 中删除所有过期条目，并返回删除数量
    # 但我们需要在删除前获取 value（本地文件路径），所以手动遍历
    now = time.time()
    try:
        for key in list(cache):
            # 尝试获取，如果已过期 get 会返回 None
            # 但我们用 cache.peek 看原始值（不受过期影响）   
            try:
                # 检查是否过期：通过直接 get 来判断
                value = cache.get(key)
                if value is not None:
                    # 未过期，跳过
                    continue
            except KeyError:
                continue

            # 已过期，尝试用 pop 获取并删除
            try:
                local_path = cache.pop(key)
                if local_path and os.path.exists(local_path):
                    os.remove(local_path)
                    log.info(f"[DiskCache] 清理过期文件: {key} -> {local_path}")
                    cleaned += 1
            except (KeyError, OSError) as e:
                log.warning(f"[DiskCache] 清理文件失败: {key}, error={e}")

    except Exception as e:
        log.error(f"[DiskCache] 清理过期文件异常: {e}", exc_info=True)

    # 调用 expire() 确保 SQLite 中的过期条目被清除
    cache.expire()

    if cleaned > 0:
        log.info(f"[DiskCache] 本轮清理了 {cleaned} 个过期文件")
    return cleaned


def start_cleanup_thread(interval: int = 60) -> threading.Thread:
    """
    启动后台清理线程，定期删除过期缓存对应的本地文件。

    Args:
        interval: 清理间隔（秒），默认 60 秒

    Returns:
        清理线程实例
    """
    def _cleanup_loop():
        log.info(f"[DiskCache] 过期清理线程启动，间隔 {interval}s")
        while True:
            try:
                cleanup_expired_files()
            except Exception as e:
                log.error(f"[DiskCache] 清理线程异常: {e}", exc_info=True)
            time.sleep(interval)

    t = threading.Thread(
        target=_cleanup_loop,
        name="diskcache-cleanup",
        daemon=True,
    )
    t.start()
    return t
