"""
调度服务：公平调度任务到RabbitMQ
"""
import json
import time
import signal
import sys
from typing import List, Set
from celery_mq.celery_app import celery_app
from config.config import my_config, ENV
from celery_mq.task_manager import task_manager
from utils.log_utils import logger as log


class DispatcherService:
    """调度服务主类"""
    
    def __init__(self):
        """初始化调度服务"""
        self.running = False
        self.queue_name = "video_queue"
        self.dispatch_interval = 2  # 调度间隔（秒）
        self.vip_task_count = 3  # VIP用户每次取出的任务数
        self.normal_task_count = 1  # 普通用户每次取出的任务数
        self.max_queue_length = 100  # RabbitMQ队列最大长度阈值
        
        # 注册信号处理
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """信号处理函数"""
        log.info(f"收到信号 {signum}，准备关闭调度服务...")
        self.stop()
        sys.exit(0)
    
    
    def check_flow_control(self) -> bool:
        """
        流控检查：检查RabbitMQ队列长度
        
        Returns:
            True表示可以继续分发，False表示需要暂停
        """
        try:
            # 使用Celery的inspect API检查队列长度
            inspect = celery_app.control.inspect()
            active_queues = inspect.active_queues()
            
            if not active_queues:
                # 如果没有活跃的worker，可以继续分发
                return True
            
            # 统计所有worker的队列长度（简化处理，实际可以通过RabbitMQ Management API获取）
            # 这里暂时返回True，实际生产环境应该通过RabbitMQ Management API查询
            return True
        except Exception as e:
            log.error(f"检查流控时出错: {e}")
            return True  # 出错时允许继续分发
    
    def publish_to_rabbitmq(self, task_id: str):
        """
        发布任务到RabbitMQ队列（使用Celery API）
        
        Args:
            task_id: 任务ID（任务数据已在Redis中）
        """
        try:
            # 使用Celery的send_task方法发送任务
            from celery_mq.task.normalize_video_tasks import process_video_task
            
            result = process_video_task.apply_async(
                args=[task_id],
                queue=self.queue_name
            )
            
            log.info(f"任务已发布到RabbitMQ: task_id={task_id}, celery_task_id={result.id}")
        except Exception as e:
            log.error(f"发布任务到RabbitMQ失败: task_id={task_id}, error={e}")
            raise
    
    def weighted_round_robin(self) -> List[str]:
        """
        加权轮询算法：VIP用户优先，普通用户轮询
        
        Returns:
            待分发的任务ID列表
        """
        tasks_to_dispatch = []
        
        # 获取活跃用户
        active_users = task_manager.get_active_users()
        if not active_users:
            return tasks_to_dispatch
        
        # 获取VIP用户
        vip_users = set(task_manager.get_vip_users())
        normal_users = [uid for uid in active_users if uid not in vip_users]
        
        # VIP用户优先处理，每人取出N个任务
        for user_id in vip_users:
            if user_id in active_users:
                user_tasks = task_manager.fetch_tasks_from_user_queue(
                    user_id, 
                    count=self.vip_task_count
                )
                tasks_to_dispatch.extend(user_tasks)
                log.info(f"VIP用户 {user_id} 取出 {len(user_tasks)} 个任务")
        
        # 普通用户轮询，每人取出1个任务
        for user_id in normal_users:
            user_tasks = task_manager.fetch_tasks_from_user_queue(
                user_id,
                count=self.normal_task_count
            )
            if user_tasks:
                tasks_to_dispatch.extend(user_tasks)
                log.info(f"普通用户 {user_id} 取出 {len(user_tasks)} 个任务")
        
        return tasks_to_dispatch
    
    def fetch_and_dispatch(self):
        """按策略抓取任务并分发"""
        # 检查流控
        if not self.check_flow_control():
            return
        
        # 加权轮询获取任务
        tasks_to_dispatch = self.weighted_round_robin()
        
        if not tasks_to_dispatch:
            return
        
        # 分发任务到RabbitMQ
        for task_id in tasks_to_dispatch:
            try:
                # 验证任务数据是否存在
                task_data = task_manager.get_task_data(task_id)
                if not task_data:
                    log.error(f"任务数据不存在: task_id={task_id}")
                    task_manager.update_task_status(task_id, "failed", error="任务数据不存在")
                    continue
                
                # 发布到RabbitMQ（只发送task_id）
                self.publish_to_rabbitmq(task_id)
                
                # 更新任务状态为dispatched
                task_manager.update_task_status(task_id, "dispatched")
                
            except Exception as e:
                log.error(f"分发任务失败: task_id={task_id}, error={e}")
                task_manager.update_task_status(task_id, "failed", error=str(e))
    
    def dispatch_loop(self):
        """主调度循环"""
        log.info("调度循环开始")
        
        while self.running:
            try:
                # 执行调度
                self.fetch_and_dispatch()
                
                # 等待指定时间
                time.sleep(self.dispatch_interval)
                
            except Exception as e:
                log.error(f"调度循环出错: {e}", exc_info=True)
                time.sleep(5)  # 出错后等待5秒再继续
    
    def start(self):
        """启动调度服务"""
        log.info("启动调度服务...")
        self.running = True
        
        # 启动调度循环
        try:
            self.dispatch_loop()
        except KeyboardInterrupt:
            log.info("收到键盘中断信号")
        finally:
            self.stop()
    
    def stop(self):
        """停止调度服务"""
        log.info("停止调度服务...")
        self.running = False
        log.info("调度服务已停止")


if __name__ == "__main__":
    dispatcher = DispatcherService()
    dispatcher.start()

