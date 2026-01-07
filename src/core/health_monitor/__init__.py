"""
健康监控模块：提供进程健康监控、心跳检查、任务超时检查等功能
"""
from core.health_monitor.service import HealthMonitorService, health_monitor_service
from core.health_monitor.heartbeat_checker import HeartbeatChecker
from core.health_monitor.timeout_checker import TaskTimeoutChecker
from core.health_monitor.restart_handler import ProcessRestartHandler
from core.health_monitor.reassignment_handler import TaskReassignmentHandler
from core.health_monitor.monitor import ProcessHealthMonitor, process_health_monitor
from core.health_monitor.lifespan import start_health_monitor, stop_health_monitor

# 向后兼容：保持旧的导入路径可用
__all__ = [
    'HealthMonitorService', 'health_monitor_service',
    'HeartbeatChecker',
    'TaskTimeoutChecker',
    'ProcessRestartHandler',
    'TaskReassignmentHandler',
    'ProcessHealthMonitor', 'process_health_monitor',
    'start_health_monitor', 'stop_health_monitor',
]



