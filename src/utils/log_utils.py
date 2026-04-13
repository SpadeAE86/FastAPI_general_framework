"""
日志工具
使用 loguru ，能自动处理异常堆栈、颜色高亮，并且线程安全
"""
import threading
import os
import sys
import time
from loguru import logger
from functools import wraps
from pathlib import Path
from typing import Union

from config.config import MY_CONFIG, ENV, LOGS_DIR


def log_to_file(log_file: Union[Path, str], level: str = 'TRACE'):
    """
    文件日志
    :param log_file:
    :param level:
    :return:
    """
    os.makedirs(LOGS_DIR, exist_ok=True)

    # 统一路径和文件名后缀
    if isinstance(log_file, str):
        log_file = Path(log_file)
    log_file = LOGS_DIR / f'{log_file.name}.log'

    # 添加文件日志
    logger.add(
        log_file,
        format='<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:1.1}</level> | <yellow>{process}</yellow>:<yellow>{thread}</yellow> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - {message}',
        level=level,
        rotation='100 MB',
        retention=5,
        compression='zip',
        enqueue=True,  # 🌟 重要：开启异步写入，防止日志 IO 阻塞你的主逻辑（尤其是音视频处理）
        encoding='utf-8'  # 显式指定编码，防止 Windows 下乱码
    )


def time_it(func):
    """
    记录时间装饰器
    :param func:
    :return:
    """
    max_time: float = 180

    @wraps(func)
    def wrapper(*args, **kwargs):
        # 当日志等级大于 TRACE 时，直接运行，不计时
        if logger.level(LOG_LEVEL).no > logger.level('TRACE').no:
            return func(*args, **kwargs)

        func_name = func.__name__
        stop_event = threading.Event()

        # 监控函数
        def monitor_task():
            count = 0
            while not stop_event.wait(1):  # 每秒检查一次 stop_event
                count += 1
                if count % 10 == 0:
                    logger.trace(f'⏳ [监控] 函数 [{func_name}] 已运行 {count}s...')

                if count >= max_time:
                    # 注意：子线程抛异常不会杀掉主线程
                    # 我们在这里记录并让主线程在结束后感知
                    logger.warning(f'🚨 [监控] 函数 [{func_name}] 运行已达 {max_time}s 限制，已运行 {count}s！')
                    # break

        # 开启守护线程
        t = threading.Thread(target=monitor_task, daemon=True)
        t.start()

        try:
            start_time = time.perf_counter()
            logger.trace(f'🚀 函数 [{func_name}] 开始执行')
            _result = func(*args, **kwargs)
            actual_duration = time.perf_counter() - start_time
            logger.trace(f'✅ 函数 [{func_name}] 执行完毕，总耗时: {actual_duration:.4f}s')

            # # 检查是否真的跑太久了 # todo
            # if actual_duration >= max_time:
            #     from exceptions.FuncException import ExecutionTimeoutError
            #     raise ExecutionTimeoutError(
            #         f'函数 [{func_name}] 实际耗时 {actual_duration:.2f}s，超过 {max_time}s 限制')
            return _result

        finally:
            # 无论成功还是报错，通知监控线程退出
            stop_event.set()
            # 显式等待监控线程结束（可选，防止日志交织）
            t.join(0.1)
            # logger.trace(f'✅ 函数 [{func_name}] 运行结束，监控线程已释放')

    return wrapper


@time_it
def __test_time_it():
    time.sleep(5)


# --- 日志 配置 ---
LOG_LEVEL = MY_CONFIG['log'][ENV]['level'].upper()

# --- 日志 初始化 ---
logger.remove()  # 移除默认
logger.add(
    sys.stderr,
    format='<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:1.1}</level> | <yellow>{process}</yellow>:<yellow>{thread}</yellow> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - {message}',
    level=LOG_LEVEL,
    enqueue=True,  # 🌟 重要：开启异步写入，防止日志 IO 阻塞你的主逻辑（尤其是音视频处理）
)

if __name__ == '__main__':
    # ----------------------------------------------------
    # 测试
    # ----------------------------------------------------

    # 测试文件日志
    log_to_file(__file__, level='TRACE')

    # 测试打印日志
    logger.trace('我是 trace')
    logger.debug('我是 debug')
    logger.info('我是 info')
    logger.success('我是 success')
    logger.warning('我是 warning')
    logger.error('我是 error')
    try:
        result = 1 / 0
    except ZeroDivisionError:
        # 会自动打印 Error 信息以及完整的 Traceback 堆栈
        logger.exception('除零错误发生')
    logger.critical('我是 critical')

    # 测试计时函数
    __test_time_it()