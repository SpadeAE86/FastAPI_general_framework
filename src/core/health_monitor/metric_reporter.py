"""
监控指标上报服务
将 RabbitMQ 队列监控数据上报到华为云 CES
"""
import threading
import time
from typing import Optional, List, Dict, Any
from utils.ces_client import get_ces_client, CESClient
from utils.rabbitmq_management import RabbitMQManagementClient
from config.config import my_config, ENV
from utils.log_utils import logger as log


class MetricReporter:
    """监控指标上报服务"""
    
    def __init__(self):
        """初始化监控指标上报服务"""
        ces_config = my_config.get("huawei_ces", {}).get(ENV, {})
        monitoring_config = my_config.get("monitoring", {})
        
        self.enabled = ces_config.get("enabled", False)
        self.report_interval = ces_config.get("report_interval", 30)  # 默认30秒
        self.queue_name = monitoring_config.get("queue_name", "video_queue")  # 监控的队列名称
        self.namespace = monitoring_config.get("namespace", "celery.rabbitmq")  # 指标命名空间
        self.metric_name = monitoring_config.get("metric_name", "rabbitmq_queue_length")  # 指标名称
        self.ttl = monitoring_config.get("ttl", 604800)  # 数据有效期7天
        
        # 初始化客户端
        self.ces_client: Optional[CESClient] = None
        self.rabbitmq_client: Optional[RabbitMQManagementClient] = None
        
        if self.enabled:
            self.ces_client = get_ces_client()
            if not self.ces_client:
                log.warning("CES 客户端初始化失败，监控指标上报将被禁用")
                self.enabled = False
            else:
                self.rabbitmq_client = RabbitMQManagementClient()
                log.info(
                    f"监控指标上报服务已初始化: "
                    f"队列={self.queue_name}, "
                    f"上报间隔={self.report_interval}秒"
                )
        else:
            log.info("监控指标上报服务未启用")
        
        # 服务状态
        self.running = False
        self.report_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def _collect_queue_metrics(self) -> Optional[int]:
        """
        收集队列监控指标
        
        Returns:
            队列消息数量，如果获取失败返回 None
        """
        if not self.rabbitmq_client:
            return None
        
        try:
            queue_length = self.rabbitmq_client.get_queue_length(self.queue_name)
            return queue_length
        except Exception as e:
            log.error(f"获取队列 {self.queue_name} 长度失败: {e}", exc_info=True)
            return None
    
    def _build_metric_data(self, queue_length: int) -> List[Dict[str, Any]]:
        """
        构建监控指标数据
        
        Args:
            queue_length: 队列消息数量
            
        Returns:
            监控指标数据列表
        """
        # 获取当前时间戳（毫秒）
        collect_time = int(time.time() * 1000)
        
        metric_data = [{
            "metric": {
                "namespace": self.namespace,
                "metric_name": self.metric_name,
                "dimensions": [{
                    "name": "queue_name",
                    "value": self.queue_name
                }]
            },
            "ttl": self.ttl,
            "collect_time": collect_time,
            "value": queue_length,
            "unit": "count"
        }]
        
        return metric_data
    
    def _report_metrics(self):
        """上报监控指标"""
        if not self.enabled or not self.ces_client:
            return
        
        # 收集队列指标
        queue_length = self._collect_queue_metrics()
        if queue_length is None:
            log.warning(f"无法获取队列 {self.queue_name} 的长度，跳过本次上报")
            return
        
        # 构建指标数据
        metric_data = self._build_metric_data(queue_length)
        
        # 上报到 CES
        success = self.ces_client.create_metric_data(metric_data)
        if success:
            log.debug(
                f"成功上报监控指标: 队列={self.queue_name}, "
                f"消息数量={queue_length}"
            )
        else:
            log.warning(
                f"上报监控指标失败: 队列={self.queue_name}, "
                f"消息数量={queue_length}"
            )
    
    def _report_loop(self):
        """上报循环"""
        log.info("监控指标上报线程已启动")
        
        while self.running and not self._stop_event.is_set():
            try:
                # 上报指标
                self._report_metrics()
                
                # 等待下次上报
                self._stop_event.wait(timeout=self.report_interval)
                
            except Exception as e:
                log.error(f"监控指标上报循环出错: {e}", exc_info=True)
                # 出错后等待一段时间再继续
                self._stop_event.wait(timeout=5)
        
        log.info("监控指标上报线程已停止")
    
    def start(self):
        """启动监控指标上报服务"""
        if not self.enabled:
            log.info("监控指标上报服务未启用，跳过启动")
            return
        
        if self.running:
            log.warning("监控指标上报服务已在运行中")
            return
        
        log.info("启动监控指标上报服务...")
        self.running = True
        self._stop_event.clear()
        
        # 启动上报线程
        self.report_thread = threading.Thread(
            target=self._report_loop,
            name="MetricReporter",
            daemon=True
        )
        self.report_thread.start()
        
        log.info("监控指标上报服务已启动")
    
    def stop(self):
        """停止监控指标上报服务"""
        if not self.running:
            return
        
        log.info("停止监控指标上报服务...")
        self.running = False
        self._stop_event.set()
        
        # 等待线程结束
        if self.report_thread:
            self.report_thread.join(timeout=5)
        
        log.info("监控指标上报服务已停止")


# 全局服务实例
metric_reporter = MetricReporter()

