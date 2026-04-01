from celery import signals

from utils.log_utils import logger as log

@signals.worker_ready.connect
def start_cache_cleanup(**kwargs):
    """
    Celery worker 启动回调
    """
    log.info("[signals] diskcache is ready and self-managed")
