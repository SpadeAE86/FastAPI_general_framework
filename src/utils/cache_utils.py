import os
import time
import threading
from typing import Optional

import diskcache
from utils.log_utils import logger as log

# --- 路径配置 ---
# SQLite 数据库目录（存放 diskcache 的索引/元数据）
_DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "cache", "obs_db"))
# 物理文件存储目录（存放实际下载的视频/音频文件）
_FILES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "cache", "obs_files"))

os.makedirs(_DB_DIR, exist_ok=True)
os.makedirs(_FILES_DIR, exist_ok=True)

# --- TTL 配置 ---
# 逻辑 TTL：决定缓存命中/未命中的时间窗口
LOGICAL_TTL = 600    # 10 分钟
# 物理 TTL：实际过期时间，GC 在这个窗口内读取路径删文件
PHYSICAL_TTL = 1800  # 30 分钟

# key 前缀约定
L_PFX = "L:"  # 逻辑 key：存 True
P_PFX = "P:"  # 物理 key：存 local_path

# --- 初始化全局缓存实例 ---
cache = diskcache.Cache(
    _DB_DIR,
    size_limit=2 * (1024 ** 3)
)
log.info(f"[OBSFileCache] 初始化完成. DB: {_DB_DIR}, Files: {_FILES_DIR}")



# --- 业务 API ---

def get_cached_path(obs_key: str) -> Optional[str]:
    """
    查询 obs_key 对应的本地文件路径。

    命中逻辑： L:{obs_key} 有效 → 返回 P:{obs_key} 的路径，并庌期双 key。
    未命中： L:{obs_key} 当作不存在→ 返回 None。
    """
    l_key = L_PFX + obs_key
    p_key = P_PFX + obs_key

    # 逻辑 key 是否存活（可能已过少10分钟逻辑 TTL）
    if cache.get(l_key) is None:
        return None

    local_path = cache.get(p_key)
    if local_path is None:
        # 物理 key 也丢了（应该不会发生，防御）
        return None

    # 容错：索引存在但物理文件被外部手动删了
    if not os.path.exists(local_path):
        log.warning(f"[OBSFileCache] 索引存在但物理文件丢失，清理条目: {obs_key}")
        cache.delete(l_key)
        cache.delete(p_key)
        return None

    # 命中续期：双 key 都刷新
    cache.touch(l_key, expire=LOGICAL_TTL)
    cache.touch(p_key, expire=PHYSICAL_TTL)
    log.debug(f"[OBSFileCache] 命中并续期: {obs_key}")
    return local_path


def set_cached_path(obs_key: str, local_path: str) -> None:
    """
    写入缓存。

    - 如果 P:{obs_key} 已存在（同一文件之前缓存过）：重置双 key TTL。
    - 如果不存在：新建双 key。
    """
    l_key = L_PFX + obs_key
    p_key = P_PFX + obs_key

    if cache.get(p_key) is not None:
        # 物理 key 已存在，只需重置 TTL
        cache.touch(p_key, expire=PHYSICAL_TTL)
    else:
        cache.set(p_key, local_path, expire=PHYSICAL_TTL)

    # 逻辑 key 总是重置（确保逻辑 TTL 从现在起计）
    cache.set(l_key, True, expire=LOGICAL_TTL)
    log.info(f"[OBSFileCache] 写入缓存: {obs_key}, 逻辑TTL={LOGICAL_TTL}s, 物理TTL={PHYSICAL_TTL}s")




def cleanup_expired_files() -> int:
    """
    过期清理：利用双 key 设计，用公开 API 安全读取过期文件路径并删除。

    逻辑：
        1. cache.expire() 清掉真实过期（30分钟）的条目
        2. 遍历所有 P:{obs_key}（物理 key），检查 L:{obs_key} 是否还在
           - L: 不在 → 逻辑 TTL（10分钟）已过期，文件应删
           - P: 还在 → 路径仍可从 P: 读取（20分钟的 GC 窗口）
        3. 读出路径，删文件，删 P: key

    并发安全：
        全部使用 diskcache 公开 API，每个操作内部有 SQLite 事务保护。
        最坏竞态：cleanup 检查 L: 不在后，另一进程刚好 set 了同 obs_key，
        此时 cache.get(p_key) 会返回新路径 → 直接跳过，不删。
    """
    deleted_files = 0
    try:
        # Step 1：清掉真实过期（30分钟）的条目
        count = cache.expire()
        if count > 0:
            log.info(f"[OBSFileCache] expire 清理完成，释放条目数: {count}")

        # Step 2：找出逻辑过期（L: 不在但 P: 还在）的条目
        to_delete = []
        for key in list(cache):
            if not isinstance(key, str) or not key.startswith(P_PFX):
                continue
            obs_key = key[len(P_PFX):]
            l_key = L_PFX + obs_key
            if cache.get(l_key) is None:
                # 逻辑 TTL 已过，物理 key 还在，可以读到路径
                local_path = cache.get(key)
                if local_path and isinstance(local_path, str):
                    to_delete.append((key, local_path))

        if to_delete:
            log.info(f"[OBSFileCache] 逻辑过期文件: {len(to_delete)} 个，准备删除")

        # Step 3：删文件 + 删 P: key
        for p_key, local_path in to_delete:
            # 兜底：确认 L: 真的还没被续期（极小竞态窗口）
            obs_key = p_key[len(P_PFX):]
            if cache.get(L_PFX + obs_key) is not None:
                log.debug(f"[OBSFileCache] 文件已被续期，跳过删除: {obs_key}")
                continue
            try:
                cache.delete(p_key)
            except Exception:
                pass
            if os.path.exists(local_path):
                try:
                    os.remove(local_path)
                    log.info(f"[OBSFileCache] 已删除过期物理文件: {local_path}")
                    deleted_files += 1
                except Exception as e:
                    log.error(f"[OBSFileCache] 删除物理文件失败: {local_path}, error: {e}")

        return deleted_files
    except Exception as e:
        log.error(f"[OBSFileCache] 执行 expire 异常: {e}", exc_info=True)
        return 0



def gc_files() -> int:
    """
    反向 GC 扫描：清理 _FILES_DIR 下已不在 cache 里的孤立物理文件。

    执行逻辑：
        1. 递归遍历 _FILES_DIR，收集所有文件的绝对路径（全集）
        2. 遍历 cache，收集所有有效 value（应保留的文件路径集合）
        3. 全集 - 应保留集 = 孤立文件 → 删除

    注意：路径全部经过 os.path.normcase + os.path.abspath 规范化，
    避免 Windows 下 \\ 与 / 混用、大小写不一致导致误判。
    """
    deleted = 0
    try:
        # Step 1：递归扫描磁盘上的所有文件（os.walk 支持子目录）
        disk_files = set()
        for root, dirs, files in os.walk(_FILES_DIR):
            for fname in files:
                fpath = os.path.normcase(os.path.abspath(os.path.join(root, fname)))
                disk_files.add(fpath)

        if not disk_files:
            log.debug("[OBSFileCache] GC: _FILES_DIR 为空，无需清理")
            return 0

        # Step 2：cache 里所有有效 value（文件路径字符串），统一规范化
        live_files = set()
        for key in cache:
            val = cache.get(key)
            if val and isinstance(val, str):
                normalized = os.path.normcase(os.path.abspath(val))
                live_files.add(normalized)

        log.info(f"[OBSFileCache] GC: 磁盘文件数={len(disk_files)}, cache 有效文件数={len(live_files)}")

        # Step 3：删除孤立文件
        orphans = disk_files - live_files
        log.info(f"[OBSFileCache] GC: 孤立文件数={len(orphans)}")

        for fpath in orphans:
            try:
                os.remove(fpath)
                log.info(f"[OBSFileCache] GC 删除孤立文件: {fpath}")
                deleted += 1
            except Exception as e:
                log.error(f"[OBSFileCache] GC 删除失败: {fpath}, error: {e}")

        if deleted > 0:
            log.info(f"[OBSFileCache] GC 完成，删除孤立文件数: {deleted}")
        else:
            log.debug("[OBSFileCache] GC 完成，无孤立文件")

    except Exception as e:
        log.error(f"[OBSFileCache] GC 异常: {e}", exc_info=True)

    return deleted


# --- 后台清理线程 ---

def start_cleanup_thread(interval: int = 60) -> threading.Thread:
    """
    启动后台守护线程，定期执行 expire + GC。

    执行顺序：
        1. cleanup_expired_files()  → 先让 SQLite 清掉过期行
        2. gc_files()               → 再扫描磁盘，删除孤立物理文件

    interval: 每隔多少秒触发一次，默认 60 秒。
    """
    def _cleanup_loop():
        log.info(f"[OBSFileCache] 清理线程已启动，间隔: {interval}s")
        while True:
            log.info(f"[gc_files] 定时垃圾回收启动")
            cleanup_expired_files()
            gc_files()
            time.sleep(interval)

    t = threading.Thread(
        target=_cleanup_loop,
        name="diskcache-auto-cleanup",
        daemon=True,
    )
    t.start()
    return t