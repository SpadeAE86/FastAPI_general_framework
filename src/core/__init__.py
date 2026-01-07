"""
Core模块：核心功能和基础设施
提供向后兼容的导入路径
"""

# 向后兼容：重新导出健康监控相关模块
from core.health_monitor import (
    HealthMonitorService,
    health_monitor_service,
    HeartbeatChecker,
    TaskTimeoutChecker,
    ProcessRestartHandler,
    TaskReassignmentHandler,
    ProcessHealthMonitor,
    process_health_monitor,
    start_health_monitor,
    stop_health_monitor,
)

# 向后兼容：重新导出视频处理相关模块
from core.video_processing import (
    normalize_service,
    normalize_process_pool,
    caption_utils,
)

# 向后兼容：重新导出调度服务
from core.dispatcher import (
    DispatcherService,
    run_dispatcher,
)

__all__ = [
    # 健康监控
    'HealthMonitorService', 'health_monitor_service',
    'HeartbeatChecker',
    'TaskTimeoutChecker',
    'ProcessRestartHandler',
    'TaskReassignmentHandler',
    'ProcessHealthMonitor', 'process_health_monitor',
    'start_health_monitor', 'stop_health_monitor',
    # 视频处理
    'normalize_service',
    'normalize_process_pool',
    'caption_utils',
    # 调度服务
    'DispatcherService',
    'run_dispatcher',
]



