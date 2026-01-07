"""
调度服务模块：负责任务调度和分发
"""
from core.dispatcher.service import DispatcherService
from core.dispatcher.run import main as run_dispatcher

__all__ = ['DispatcherService', 'run_dispatcher']

