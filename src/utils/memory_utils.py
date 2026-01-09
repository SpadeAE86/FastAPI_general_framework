from cachetools import TTLCache
import os
from utils.log_utils import logger as log
import threading
from config.config import *

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
            if key not in self.refresh and my_config["direct_download"]:
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