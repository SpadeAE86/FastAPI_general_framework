from typing import Optional

from celery import signals
import threading
import redis
import os

from config.config import VIDEO_CACHE_PREFIX, VIDEO_CACHE_BASE_PREFIX, my_config, ENV
from utils.log_utils import logger as log
from utils.redis_client import RedisClientFactory



db = my_config.get("redis").get(ENV).get("database")
log.info(f"listening on {db}")
def redis_evict_listener():
    r = RedisClientFactory.get_client()
    version_str = redis.__version__  # e.g. "4.5.5"
    log.info(f"redis version is {version_str}")
    version_tuple = tuple(int(x) for x in version_str.split("."))  # (4, 5, 5)

    pubsub = r.pubsub()
    pubsub.psubscribe(f"__keyevent@{db}__:expired")

    for msg in pubsub.listen():
        if msg["type"] != "pmessage":
            continue

        if version_tuple >= (4, 0, 0):
            key = msg["data"]
        else:
            key = msg["data"].decode()

        # 使用 Base Prefix 匹配，这样可以捕获上次 crash 遗留的 key（它们有不同的 Instance ID）
        if not key.startswith(VIDEO_CACHE_BASE_PREFIX):
            continue

        # 动态解析 Path：Prefix 格式为 "Base_InstanceID:Path"
        # 我们分割一次 ":" 即可拿到后面的 Path
        try:
            # key e.g. "aigc_video_cache_test_1234abcd:path/to/file"
            # split(":", 1) -> ["aigc_video_cache_test_1234abcd", "path/to/file"]
            parts = key.split(":", 1)
            if len(parts) < 2:
                log.warning(f"[RedisEvict] Ignored malformed key: {key}")
                continue
            
            local_path = r.get(key)
            if os.path.exists(local_path):
                os.remove(local_path)
                log.info(f"[RedisEvict] removed {local_path} (from key {key})")
        except Exception as e:
            log.exception(e)


@signals.worker_ready.connect
def start_redis_listener(**kwargs):
    # 确保开启了键过期事件通知
    try:
        r = RedisClientFactory.get_client()
        config = r.config_get("notify-keyspace-events")
        current_config = config.get("notify-keyspace-events", "")
        if "E" not in current_config or "x" not in current_config:
            log.info(f"Updating notify-keyspace-events from '{current_config}' to 'Ex'")
            r.config_set("notify-keyspace-events", "Ex")
    except Exception as e:
        log.error(f"Failed to config redis notify-keyspace-events: {e}")

    log.info("[signals] redis eviction loop injected")
    t = threading.Thread(
        target=redis_evict_listener,
        name="redis-evict-listener",
        daemon=True,
    )
    t.start()
