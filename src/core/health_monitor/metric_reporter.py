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
        
        # 动态获取所有要监控的队列
        self.queues = []
        task2queue = my_config.get("task_type", {})
        for _, queue_name in task2queue.items():
             # 统一加上环境变量前缀
             self.queues.append(f"{ENV}_{queue_name}")
        
        # 如果没有配置任务队列，给一个默认值兜底（虽然可能不正确，但保持原有行为）
        if not self.queues:
             self.queues.append(f"{ENV}_video_queue")

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
                    f"队列列表={self.queues}, "
                    f"上报间隔={self.report_interval}秒"
                )
        else:
            log.info("监控指标上报服务未启用")
        
        # 服务状态
        self.running = False
        self.report_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def _collect_queue_metrics(self) -> Dict[str, Optional[int]]:
        """
        收集所有配置队列的监控指标
        
        通过RabbitMQ Management API获取指定队列的消息数量（ready + unacknowledged）。
        
        Returns:
            Dict[str, Optional[int]]: 队列名到消息数量的映射
        """
        results = {}
        if not self.rabbitmq_client:
            return results
        
        for queue_name in self.queues:
            try:
                queue_length = self.rabbitmq_client.get_queue_length(queue_name)
                results[queue_name] = queue_length
            except Exception as e:
                log.error(f"获取队列 {queue_name} 长度失败: {e}", exc_info=True)
                results[queue_name] = None
        
        return results
    
    def _build_metric_data(self, queue_name: str, queue_length: int) -> Dict[str, Any]:
        """
        构建单条监控指标数据
        
        将队列长度数据转换为华为云CES API要求的格式。
        
        Args:
            queue_name: 队列名称
            queue_length: 队列消息数量，用于构建指标值
        
        Returns:
            Dict[str, Any]: 监控指标数据对象
        """
        # 获取当前时间戳（毫秒）
        collect_time = int(time.time() * 1000)
        
        return {
            "metric": {
                "namespace": self.namespace,
                "metric_name": self.metric_name,
                "dimensions": [{
                    "name": "queue_name",
                    "value": queue_name
                }]
            },
            "ttl": self.ttl,
            "collect_time": collect_time,
            "value": queue_length,
            "unit": "count"
        }
    
    async def _report_metrics(self):
        """
        上报监控指标（异步方法）
        
        收集队列指标数据，构建CES格式的指标数据，并异步上报到华为云CES服务。
        如果上报失败，会记录警告日志但不抛出异常。
        """
        if not self.enabled or not self.ces_client:
            return
        
        # 收集所有队列指标
        queue_metrics = self._collect_queue_metrics()
        if not queue_metrics:
            return
            
        # 构建指标数据列表
        metric_data_list = []
        for queue_name, length in queue_metrics.items():
            if length is not None:
                metric_data_list.append(self._build_metric_data(queue_name, length))
            else:
                 log.warning(f"无法获取队列 {queue_name} 的长度，跳过该队列上报")

        if not metric_data_list:
            return
        
        # 批量异步上报到 CES
        success = await self.ces_client.create_metric_data(metric_data_list)
        if success:
            log.debug(
                f"成功上报监控指标: 数量={len(metric_data_list)}"
            )
        else:
            log.warning(
                f"上报监控指标失败: 数量={len(metric_data_list)}"
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

