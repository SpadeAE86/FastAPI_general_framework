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
        # 使用 Base Prefix 匹配，这样可以捕获上次 crash 遗留的 key
        # 新逻辑：只处理 Shadow Key 的过期事件
        if not key.endswith(":shadow"):
            continue
        
        # 还原真实 Key:  "xxx:shadow" -> "xxx"
        real_key = key[:-7]

        # 再次检查前缀，确保是我们的业务 Key
        # 改为精准匹配当前实例的前缀，防止抢其他 Worker/服务器 的 Key，导致误删 Redis Key 却删不掉文件
        if not real_key.startswith(VIDEO_CACHE_PREFIX):
            continue

        local_path = None
        try:
            # 获取真实数据，因为 Real Key 的 TTL 比 Shadow Key 长，理论上此时一定还在
            local_path = r.get(real_key)
            if local_path:
                # 防止竞态条件：检查 real_key 的剩余 TTL
                # 如果 TTL > 3600 秒，说明 data key 刚刚被刷新过（原始 TTL = 600 + 3600 = 4200 秒）
                # 这意味着有新的下载刚刚发生，当前过期的 shadow key 是旧的、过时的
                # 此时不应删除文件，而是让新的 shadow key 在其 TTL 到期时再处理
                remaining_ttl = r.ttl(real_key)
                if remaining_ttl > 3600:
                    log.warning(f"[RedisEvict] SKIP deletion: {local_path} (shadow key {key} expired, but real key {real_key} has high TTL={remaining_ttl}s, indicating a recent refresh)")
                    continue  # 跳过删除，让最新的 shadow key 负责清理
                
                if os.path.exists(local_path):
                    os.remove(local_path)
                    log.info(f"[RedisEvict] removed {local_path} (triggered by {key})")
                else:
                    log.info(f"[RedisEvict] {local_path} no longer exists")
                # 清理掉 Real Key
                r.delete(real_key)
            else:
                log.warning(f"[RedisEvict] shadow key {key} point to Real key {real_key} -> {local_path} not found or already deleted (shadow: {key})")

        except Exception as e:
            log.exception(f"[RedisEvict] Failed to clean up {local_path}: {e}")


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
