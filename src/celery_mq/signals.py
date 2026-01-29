from typing import Optional

from celery import signals
import threading
import redis
import os
from utils.log_utils import logger as log
from utils.redis_client import RedisClientFactory

redis_client: Optional[redis.Redis] = None


def redis_evict_listener():
    r = RedisClientFactory.get_client()
    pubsub = r.pubsub()
    pubsub.psubscribe("__keyevent@0__:expired")

    for msg in pubsub.listen():
        if msg["type"] != "pmessage":
            continue

        key = msg["data"].decode()
        if not key.startswith("obs_cache:"):
            continue

        local_path = key.removeprefix("obs_cache:")
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
                log.info(f"[RedisEvict] removed {local_path}")
        except Exception as e:
            log.exception(e)


@signals.worker_ready.connect
def start_redis_listener(**kwargs):
    log.info("[signals] redis eviction loop injected")
    t = threading.Thread(
        target=redis_evict_listener,
        name="redis-evict-listener",
        daemon=True,
    )
    t.start()

@signals.worker_process_init.connect
def on_worker_process_init(**kwargs):
    log.info("[signals] redis client is created")
    global redis_client
    redis_client = RedisClientFactory.get_client()