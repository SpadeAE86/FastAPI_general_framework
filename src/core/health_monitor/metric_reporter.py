"""
监控指标上报服务
将 RabbitMQ 队列监控数据上报到华为云 CES
"""
import asyncio
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
        self.queue_name = monitoring_config.get("queue_name", f"{ENV}_video_queue")  # 监控的队列名称
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
        
        通过RabbitMQ Management API获取指定队列的消息数量（ready + unacknowledged）。
        
        Returns:
            Optional[int]: 队列消息数量，如果获取失败返回None
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
        
        将队列长度数据转换为华为云CES API要求的格式。
        
        Args:
            queue_length: 队列消息数量，用于构建指标值
        
        Returns:
            List[Dict[str, Any]]: 监控指标数据列表，包含命名空间、指标名称、维度、时间戳等信息
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
    
    async def _report_metrics(self):
        """
        上报监控指标（异步方法）
        
        收集队列指标数据，构建CES格式的指标数据，并异步上报到华为云CES服务。
        如果上报失败，会记录警告日志但不抛出异常。
        """
        if not self.enabled or not self.ces_client:
            return
        
        # 收集队列指标
        queue_length = self._collect_queue_metrics()
        if queue_length is None:
            log.warning(f"无法获取队列 {self.queue_name} 的长度，跳过本次上报")
            return
        
        # 构建指标数据
        metric_data = self._build_metric_data(queue_length)
        
        # 异步上报到 CES
        success = await self.ces_client.create_metric_data(metric_data)
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
        """
        上报循环线程函数
        
        在后台线程中创建并运行asyncio事件循环，定期执行异步指标上报。
        """
        log.info("监控指标上报线程已启动")
        
        # 创建新的事件循环用于此线程
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 运行异步上报循环
            loop.run_until_complete(self._async_report_loop())
        finally:
            loop.close()
        
        log.info("监控指标上报线程已停止")
    
    async def _async_report_loop(self):
        """
        异步上报循环
        
        在事件循环中定期执行异步指标上报，直到服务停止。
        每次上报后会等待配置的间隔时间，如果出错会等待5秒后继续。
        """
        while self.running and not self._stop_event.is_set():
            try:
                # 异步上报指标
                await self._report_metrics()
                
                # 异步等待下次上报（使用asyncio.sleep以避免阻塞事件循环）
                # 同时检查停止事件
                for _ in range(self.report_interval):
                    if self._stop_event.is_set():
                        break
                    await asyncio.sleep(1)
                
            except Exception as e:
                log.error(f"监控指标上报循环出错: {e}", exc_info=True)
                # 出错后等待一段时间再继续
                for _ in range(5):
                    if self._stop_event.is_set():
                        break
                    await asyncio.sleep(1)
    
    def start(self):
        """
        启动监控指标上报服务
        
        如果服务未启用或已在运行中，则跳过启动。
        启动后会创建一个后台线程定期上报指标。
        """
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
        """
        停止监控指标上报服务
        
        设置停止标志，等待上报线程结束（最多等待5秒）。
        如果服务未运行，则直接返回。
        """
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

