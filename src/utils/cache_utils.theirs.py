"""
文件缓存工具
使用 diskcache，进程安全，线程安全
由它自动处理过期，简化 set 和 get，处理竞态
由于主要为了缓存 video 和 audio 等数据，使用全文件保存，优化缓存文件后缀名
"""

import io
import os
import codecs
import os.path as op
from pathlib import Path
from diskcache import Cache, Disk, UNKNOWN
from typing import Union

from config.config import MY_CONFIG, ENV
from utils.log_utils import logger, time_it


# --- 自定义带文件格式后缀的 Disk 类 ---
class SuffixDisk(Disk):
    def __init__(self, directory, **kwargs):
        super().__init__(directory, **kwargs)

    def filename(self, key=UNKNOWN, value=UNKNOWN):
        """
        重写 suffix 逻辑
        :param key:
        :param value:
        :return:
        """

        # 提取文件后缀
        suffix = '.val'  # Disk 默认后缀
        if isinstance(key, str):
            _, suffix = os.path.splitext(key)

        # 原始逻辑
        hex_name = codecs.encode(os.urandom(16), 'hex').decode('utf-8')
        sub_dir = op.join(hex_name[:2], hex_name[2:4])
        name = hex_name[4:] + suffix
        filename = op.join(sub_dir, name)
        full_path = op.join(self._directory, filename)
        return filename, full_path


@time_it
def check_in_cache(key: str) -> bool:
    """
    检查是否在缓存中
    直接尝试续期，touch 会原子化地处理内部查找. 如果返回 True，说明 Key 存在且已更新过期时间
    :param key:
    :return:
    """
    return _CACHE.touch(key, expire=_CACHE_TTL)


@time_it
def set_to_cache(key: str, data: Union[bytes, io.BufferedIOBase]):
    """
    将 bytes 存入缓存
    :param key:
    :param data:可以是 bytes, 文件句柄
    :return:
    """
    # 检查数据
    assert data

    # 检查是否存在
    if check_in_cache(key):
        return

    # 新存入
    _CACHE.set(key, data, expire=_CACHE_TTL, read=True)  # 直接存储 bytes，由于 disk_min_file_size=0，它会自动触发 SuffixDisk.filename


@time_it
def get_from_cache(key: str, as_path: bool = False) -> Union[bytes, Path, None]:
    """
    获取缓存中的数据，可选返回 path
    # todo as_handle 可以直接返回文件句柄，减少一次打开的开销，但是必须注意关闭
    :param key: 
    :param as_path: 
    :return:
    """
    # 检查是否存在
    if not check_in_cache(key):
        return None

    if as_path:
        # read=True，diskcache 才会返回文件对象
        with _CACHE.get(key, read=True, default=None) as handle:  # 使用 with 确保 handle 自动关闭
            # 这种情况通常意味着索引在，但底层逻辑已失效
            if handle is None:
                logger.warning(f'⚠️ 索引存在但句柄获取失败: {key}')
                _CACHE.delete(key)
                return None

            file = Path(handle.name)
            # 检查文件状态
            if not file.exists():
                logger.warning(f'⚠️ 物理文件丢失: {file}')
                _CACHE.delete(key)  # 剔除脏数据
                return None

            return file

    else:
        # 正常读取，diskcache 检测到 raw=1 会自动读取文件内容返回 bytes
        data = _CACHE.get(key, default=None)
        # 检查临界状态
        if data is None:
            logger.warning(f'⚠️ 续期后触发自动删除: {key}')
            _CACHE.delete(key)
        return data


@time_it
def reconcile_cache_integrity():
    """
    缓存一致性校验：
    1. 清理过期索引。
    2. 遍历所有条目，检查对应的物理文件是否存在，不存在则删除索引。
    """
    logger.info("🚀 开始执行缓存一致性深度自检...")

    # 1. 清理数据库中已过期的条目
    expired_count = _CACHE.expire()

    # 2. 检查物理文件完整性
    # 注意：如果缓存量达到万级以上，此操作可能耗时几秒，建议仅在启动或低峰期执行
    broken_count = 0
    total_count = 0

    # diskcache 的迭代会返回所有 key # todo 巨量的遍历会导致启动耗时很长。虽然在 get_from_cache 中做了文件检查
    for key in list(_CACHE.iterkeys()):
        total_count += 1
        try:
            # read=True，diskcache 才会返回文件对象
            with _CACHE.get(key, read=True, default=None) as handle:  # 使用 with 确保 handle 自动关闭
                # 这种情况通常意味着索引在，但底层逻辑已失效
                if handle is None:
                    logger.warning(f'🧹 索引存在但关联丢失: {key}')
                    _CACHE.delete(key)
                    broken_count += 1
                    continue

                file_path = Path(handle.name)
                if not file_path.exists():
                    logger.warning(f'🧹 物理文件缺失: {key}')
                    _CACHE.delete(key)
                    broken_count += 1
        except Exception as e:
            # 如果 get() 失败或 handle 异常，也视为损坏
            logger.exception(f'🧹 缓存项损坏: {key}')
            _CACHE.delete(key)
            broken_count += 1

    # 统计
    current_size = _CACHE.volume()
    logger.success(
        f'✅ 自检完成! '
        f'总计条目: {total_count}, '
        f'清理过期条目: {expired_count}, '
        f'清理脏数据: {broken_count}, '
        f'当前总大小: {current_size / 1024 ** 3:.2f}GB'
    )


# --- 配置 ---
_CACHE_DIR = MY_CONFIG['cache'][ENV]['cache_dir']
os.makedirs(_CACHE_DIR, exist_ok=True)
_CACHE_MAX_SIZE = MY_CONFIG['cache'][ENV]['cache_max_size']
_CACHE_TTL = MY_CONFIG['cache'][ENV]['cache_ttl']

# --- 初始化 ---
_CACHE: Cache = Cache(
    _CACHE_DIR,  # 目录
    disk=SuffixDisk,  # 传入自定义 Disk
    size_limit=_CACHE_MAX_SIZE,  # 容量大小
    disk_min_file_size=0,  # 确保所有内容都存为文件
    eviction_policy='least-recently-used',  # 满之后优先删除使用时间最早的
)

if __name__ == '__main__':
    # ----------------------------------------------------
    # 测试
    # ----------------------------------------------------

    # 测试文件缓存一致性
    reconcile_cache_integrity()

    # 测试设置文件缓存
    from config.config import TEMP_DIR

    video_file = TEMP_DIR / 'final-1773311230041.mp4'
    with open(video_file, 'rb') as f:
        set_to_cache(str(video_file), f)

    #     video_data = f.read()
    #
    # set_to_cache(str(video_file), video_data)

    # 测试读取文件缓存
    print(f'{type(get_from_cache(str(video_file))) = }')
    print(f'{get_from_cache(str(video_file), as_path=True) = }')
