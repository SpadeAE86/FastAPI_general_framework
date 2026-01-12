"""
调度服务启动脚本
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.dispatcher.service import DispatcherService
from utils.log_utils import logger as log


def main():
    """
    调度服务主函数
    
    创建DispatcherService实例并启动调度服务。
    如果启动失败，会记录错误日志并退出程序。
    """
    log.info("=" * 50)
    log.info("调度服务启动")
    log.info("=" * 50)
    
    try:
        dispatcher = DispatcherService()
        dispatcher.start()
    except Exception as e:
        log.error(f"调度服务启动失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()




