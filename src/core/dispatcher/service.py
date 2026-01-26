"""
调度服务：公平调度任务到RabbitMQ
"""
import signal
import sys
import time
from typing import List, Dict
from collections import defaultdict
from celery_mq.task_manager import task_manager
from config.config import my_config, ENV
from utils.log_utils import logger as log
from utils.rabbitmq_management import RabbitMQManagementClient
from celery import group, chain
# from celery_mq.task import process_functions  <-- Removed to fix circular import

class DispatcherService:
    """调度服务主类"""
    
    def __init__(self):
        """初始化调度服务"""
        self.running = False
        
        # 从配置读取调度服务参数
        dispatcher_config = my_config.get("dispatcher", {})

        self.dispatch_interval = dispatcher_config.get("dispatch_interval", 1)  # 调度间隔（秒）
        self.vip_task_count = dispatcher_config.get("vip_task_count", 3)  # VIP用户每次取出的任务数
        self.normal_task_count = dispatcher_config.get("normal_task_count", 1)  # 普通用户每次取出的任务数
        self.max_queue_length = dispatcher_config.get("max_queue_length", 100)  # RabbitMQ队列最大长度阈值
        
        # 初始化 RabbitMQ Management API 客户端（缓存实例避免重复创建）
        self.rabbitmq_client = RabbitMQManagementClient()
        
        # 注册信号处理
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """
        信号处理函数
        
        处理SIGTERM和SIGINT信号，优雅地关闭调度服务。
        
        Args:
            signum: 信号编号
            frame: 当前堆栈帧
        """
        log.info(f"收到信号 {signum}，准备关闭调度服务...")
        self.stop()
        sys.exit(0)

    def check_flow_control(self) -> Dict[str, bool]:
        """
        流控检查（按 task_type 维度）

        Returns:
            Dict[task_type, bool]:
            True  -> 该任务类型可以继续分发
            False -> 该任务类型需要暂停
        """
        result = {}

        try:
            task2queue = my_config.get("task_type", {})

            for task_type, queue_name in task2queue.items():
                real_queue_name = f"{ENV}_{queue_name}"
                try:
                    queue_length = self.rabbitmq_client.get_queue_length(real_queue_name)

                    log.debug(
                        f"流控检查: task_type={task_type}, "
                        f"queue={real_queue_name}, length={queue_length}, "
                        f"threshold={self.max_queue_length}"
                    )

                    if queue_length >= self.max_queue_length:
                        log.warning(
                            f"队列流控触发: task_type={task_type}, "
                            f"queue={real_queue_name}, length={queue_length}"
                        )
                        result[task_type] = False
                    else:
                        result[task_type] = True

                except Exception as qe:
                    log.error(
                        f"获取队列长度失败: task_type={task_type}, queue={real_queue_name}, error={qe}"
                    )
                    # 单个队列失败，不影响其他队列
                    result[task_type] = True

            return result

        except Exception as e:
            log.error("流控系统异常，默认放行所有任务", exc_info=True)
            # 全异常时兜底：全部放行
            return {task_type: True for task_type in my_config.get("task_type", {})}
    
    def publish_to_rabbitmq(self, task_id: str, task_type: str, task_data: dict = None):
        """
        发布任务到RabbitMQ队列（使用Celery API）
        
        使用Celery的apply_async方法将任务发送到指定的RabbitMQ队列。
        body塞完整的请求体，header塞task_id。
        
        Args:
            task_id: 任务ID，用于标识要发布的任务
            task_type: 任务类型
            task_data: 任务数据（可选，如果不传则尝试从Redis获取）
        """
        if task_data is None:
            task_data = task_manager.get_task_data(task_id)
            if not task_data:
                 log.error(f"任务数据不存在,无法发布: task_id={task_id}")
                 raise ValueError(f"Task data missing for task_id={task_id}")
        
        try:
            # 使用Celery的send_task方法发送任务
            task2queue = my_config.get("task_type", {})
            queue_name = task2queue.get(task_type, f"{ENV}_video_queue")
            # 延迟导入，解决循环依赖
            from celery_mq.task import process_functions
            process_function = process_functions[task_type]
            
            result = process_function.apply_async(
                args=[task_data],
                queue=queue_name,
                delivery_mode=2,
                headers={"task_id": task_id}
            )
            
            log.info(f"任务已发布到RabbitMQ: task_id={task_id}, celery_task_id={result.id}")
        except Exception as e:
            log.error(f"发布任务到RabbitMQ失败: task_id={task_id}, error={e}")
            raise
    
    def weighted_round_robin(self) -> List[str]:
        """
        加权轮询算法：VIP用户优先，普通用户轮询
        
        实现加权轮询调度策略：
        1. 首先处理所有VIP用户，每个VIP用户取出配置数量的任务（默认3个）
        2. 然后处理普通用户，每个普通用户取出1个任务
        3. 确保VIP用户的任务优先被分发
        
        Returns:
            List[str]: 待分发的任务ID列表，按优先级排序
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
        """
        按策略抓取任务并分发
        
        执行一次完整的调度周期：
        1. 检查流控（队列长度是否超过阈值）
        2. 使用加权轮询算法获取待分发的任务
        3. 批量验证任务数据是否存在
        4. 批量发布任务到RabbitMQ（使用Celery group提升性能）
        5. 批量更新任务状态为dispatched
        """
        # 检查流控
        flow_control = self.check_flow_control()
        
        # 加权轮询获取任务
        tasks_to_dispatch = self.weighted_round_robin()
        
        if not tasks_to_dispatch:
            return
        
        log.info(f"本轮调度获取到 {len(tasks_to_dispatch)} 个任务，开始批量分发")
        
        # 批量验证和分发任务
        valid_tasks = defaultdict(list)
        failed_tasks = []
        
        # 第一步：批量验证任务数据
        for task_id in tasks_to_dispatch:
            try:
                task_data = task_manager.get_task_data(task_id)
                if not task_data:
                    log.error(f"任务数据不存在: task_id={task_id}")
                    failed_tasks.append((task_id, "任务数据不存在"))
                else:
                    task_type = task_data.get("task_type", "mix")
                    valid_tasks[task_type].append((task_id, task_data))
            except Exception as e:
                log.error(f"验证任务数据失败: task_id={task_id}, error={e}")
                failed_tasks.append((task_id, str(e)))

        # 第二步：按 task_type 批量发布任务到 RabbitMQ
        for task_type, task_items in valid_tasks.items():

            # 流控检查（task_type 级别）
            if not flow_control.get(task_type, True):
                log.info(f"任务类型被流控，暂不分发: task_type={task_type}")
                continue

            # 先尝试 batch 发布
            try:
                self.batch_publish_to_rabbitmq(task_type, task_items)
                log.info(
                    f"批量发布成功: task_type={task_type}, count={len(task_items)}"
                )

                # batch 成功后，统一更新状态
                for task_id, _ in task_items:
                    try:
                        task_manager.update_task_status(task_id, "dispatching")
                    except Exception as e:
                        log.error(
                            f"更新任务状态失败: task_id={task_id}, "
                            f"task_type={task_type}, error={e}"
                        )

            except Exception as e:
                log.error(
                    f"批量发布失败: task_type={task_type}, error={e}",
                    exc_info=True,
                )
                log.warning(
                    f"task_type={task_type} 批量发布失败，降级为逐个发布"
                )

                # ⚠️ 关键点：只降级这一种 task_type
                for task_id, task_data in task_items:
                    try:
                        self.publish_to_rabbitmq(task_id, task_type, task_data=task_data)
                        task_manager.update_task_status(task_id, "dispatching")
                    except Exception as e2:
                        log.error(
                            f"发布任务失败: task_id={task_id}, "
                            f"task_type={task_type}, error={e2}"
                        )
                        failed_tasks.append((task_id, str(e2)))

        # 第三步：批量更新任务状态（valid_tasks: Dict[str, List[Tuple[str, dict]]]）
        for task_type, task_items in valid_tasks.items():
            for task_id, _ in task_items:
                try:
                    task_manager.update_task_status(task_id, "dispatched")
                except Exception as e:
                    log.error(
                        f"更新任务状态失败: task_id={task_id}, "
                        f"task_type={task_type}, error={e}"
                    )

        # 第四步：处理失败任务
        for task_id, error in failed_tasks:
            try:
                task_manager.update_task_status(task_id, "failed", error=error)
            except Exception as e:
                log.error(
                    f"更新失败任务状态出错: task_id={task_id}, error={e}"
                )

        if failed_tasks:
            log.warning(f"本轮调度有 {len(failed_tasks)} 个任务失败")

    def batch_publish_to_rabbitmq(self, task_type: str, task_items: List[tuple]):
        """
        批量发布同一 task_type 的任务到 RabbitMQ
        
        Args:
            task_type: 任务类型
            task_items: List[Tuple(task_id, task_data)]

        使用 Celery group 批量发送任务。
        注意：
        - 该方法不保证“全成功或全失败”
        - 抛异常仅表示发布过程中出现客户端异常
        - 不做任何状态更新或补偿逻辑
        """
        if not task_items:
            return

        try:
            task2queue = my_config.get("task_type", {})
            queue_name = task2queue.get(task_type, f"{ENV}_video_queue")
            # 延迟导入，解决循环依赖
            from celery_mq.task import process_functions
            process_function = process_functions[task_type]

            task_signatures = [
                process_function.s(task_data).set(
                    queue=queue_name,
                    delivery_mode=2,  # 持久化消息
                    headers={"task_id": task_id}
                )
                for task_id, task_data in task_items
            ]

            job = group(task_signatures)
            result = job.apply_async()

            log.info(
                f"批量发布任务到RabbitMQ成功: "
                f"task_type={task_type}, count={len(task_items)}, group_id={result.id}"
            )

        except Exception as e:
            log.error(
                f"批量发布任务到RabbitMQ失败: "
                f"task_type={task_type}, count={len(task_items)}, error={e}",
                exc_info=True,
            )
            raise

    def dispatch_loop(self):
        """
        主调度循环
        
        持续执行调度操作，每次调度后等待配置的间隔时间。
        如果调度过程中出错，会等待5秒后继续，避免因临时错误导致调度完全停止。
        """
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
        """
        启动调度服务
        
        设置运行标志为True，然后启动主调度循环。
        如果收到键盘中断信号（KeyboardInterrupt），会优雅地停止服务。
        """
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
        """
        停止调度服务
        
        设置运行标志为False，调度循环会在下次迭代时退出。
        """
        log.info("停止调度服务...")
        self.running = False
        log.info("调度服务已停止")


if __name__ == "__main__":
    dispatcher = DispatcherService()
    dispatcher.start()

