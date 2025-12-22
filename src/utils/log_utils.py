import logging, sys
from logging import Formatter

class ColoredFormatter(Formatter):
    """自定义带颜色的日志格式化器"""
    COLORS = {
        'DEBUG': '\033[36m',  # 青色
        'INFO': '\033[32m',  # 绿色
        'WARNING': '\033[33m',  # 黄色
        'ERROR': '\033[31m',  # 红色
        'CRITICAL': '\033[1;31m'  # 红色加粗
    }
    RESET = '\033[0m'

    def format(self, record):
        # 获取默认格式
        msg = super().format(record)
        # 添加颜色
        if record.levelname in self.COLORS:
            msg = f"{self.COLORS[record.levelname]}{record.levelname.upper()}:\t{msg}"
        return msg


def setup_logger():
    """配置全局logger"""
    RESET = '\033[0m'
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = ColoredFormatter(
        f'[%(asctime)s][%(threadName)s][%(funcName)s]{RESET} %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# 初始化logger
setup_logger()
logger = logging.getLogger(__name__)