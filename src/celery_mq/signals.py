from typing import Optional

from celery import signals
import threading
import redis
import os

from config.config import VIDEO_CACHE_PREFIX, my_config, ENV
from utils.log_utils import logger as log
from utils.redis_client import RedisClientFactory



db = my_config.get("redis").get(ENV).get("database")
log.info(f"listening on {db}")
def redis_evict_listener():
    r = RedisClientFactory.get_client()
    pubsub = r.pubsub()
    pubsub.psubscribe(f"__keyevent@{db}__:expired")

    for msg in pubsub.listen():
        if msg["type"] != "pmessage":
            continue

        key = msg["data"].decode()
        if not key.startswith(VIDEO_CACHE_PREFIX):
            continue

        local_path = key.removeprefix(VIDEO_CACHE_PREFIX)
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
                log.info(f"[RedisEvict] removed {local_path}")
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
