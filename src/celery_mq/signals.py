from celery import signals

from utils.log_utils import logger as log
from utils.cache_utils import start_cleanup_thread


@signals.worker_ready.connect
def start_cache_cleanup(**kwargs):
    """
    Celery worker 启动后，启动 diskcache 过期清理线程。

    定期扫描 diskcache 中过期的条目，删除对应的本地文件。
    替代原来的 Redis pubsub shadow key 过期监听机制。
    """
    log.info("[signals] diskcache cleanup thread injected")
    start_cleanup_thread(interval=60)
