"""
Worker检查器：负责检查Celery worker的存活状态和数量
"""
import os
import socket
import re
from typing import List, Dict, Any, Set, Optional, Tuple
from celery_mq.celery_app import celery_app
from core.health_monitor.monitor import process_health_monitor
from utils.process_utils import parse_process_id
from utils.env_utils import (
    extract_env_from_worker_name,
    is_same_env,
    extract_hostname_from_worker_name
)
from utils.log_utils import logger as log
from config.config import ENV


class WorkerChecker:
    """Worker检查器"""
    
    def __init__(self, min_healthy_workers: int = 1):
        """
        初始化Worker检查器
        
        Args:
            min_healthy_workers: 最小健康worker数量
        """
        self.min_healthy_workers = min_healthy_workers
        # 获取当前机器的主机名
        self.local_hostname = socket.gethostname()
        # 获取当前环境
        self.current_env = ENV
        log.info(f"WorkerChecker初始化，当前主机名: {self.local_hostname}, 当前环境: {self.current_env}")
    
    def get_active_workers_from_celery(self) -> Set[str]:
        """
        使用Celery inspect API获取活跃worker列表，并过滤出当前环境的worker
        
        通过Celery的inspect API获取所有活跃的worker，然后根据环境标识过滤出
        属于当前环境的worker（如_local、_test、_prod等）。
        
        Returns:
            Set[str]: 当前环境的活跃worker名称集合，格式为 {"worker_name@hostname", ...}
        """
        try:
            inspect = celery_app.control.inspect()
            
            # 获取活跃worker列表
            active_workers = inspect.active()
            if active_workers is None:
                log.warning("无法获取Celery活跃worker列表（可能没有worker连接）")
                return set()
            
            # active_workers格式: {"worker_name@hostname": [...], ...}
            all_worker_names = set(active_workers.keys())
            
            # 过滤出当前环境的worker
            filtered_workers = set()
            filtered_out_count = 0
            for worker_name in all_worker_names:
                if is_same_env(worker_name, self.current_env):
                    filtered_workers.add(worker_name)
                else:
                    filtered_out_count += 1
                    # 检查被过滤的原因
                    worker_env = extract_env_from_worker_name(worker_name)
                    if worker_env is None:
                        reason = "worker名称缺少环境标识"
                    else:
                        reason = f"环境不匹配 (worker环境: {worker_env}, 当前环境: {self.current_env})"
                    log.debug(f"过滤掉worker: {worker_name}, 原因: {reason}")
            
            if filtered_out_count > 0:
                log.info(
                    f"环境过滤: 从Celery活跃worker中过滤掉 {filtered_out_count} 个worker "
                    f"(总worker数: {len(all_worker_names)}, 当前环境worker数: {len(filtered_workers)}, 当前环境: {self.current_env})"
                )
            
            log.debug(f"从Celery获取到 {len(filtered_workers)} 个当前环境的活跃worker: {filtered_workers}")
            return filtered_workers
            
        except Exception as e:
            log.error(f"获取Celery活跃worker列表失败: {e}", exc_info=True)
            return set()
    
    def get_registered_processes_from_redis(self) -> Dict[str, Dict[str, Any]]:
        """
        从Redis获取所有已注册的进程
        
        从Redis的进程集合中获取所有已注册的进程ID，然后查询每个进程的详细状态信息。
        
        Returns:
            Dict[str, Dict[str, Any]]: 进程信息字典，key为"worker_name:pid"格式的字符串，
                value为进程状态信息字典，包含worker_name、pid、status、current_task等字段
        """
        processes = {}
        try:
            all_processes = process_health_monitor.get_all_processes()
            
            for process_str in all_processes:
                parsed = parse_process_id(process_str)
                if parsed is None:
                    continue
                
                worker_name, pid = parsed
                process_status = process_health_monitor.get_process_status(worker_name, pid)
                
                if process_status:
                    processes[process_str] = process_status
            
            log.debug(f"从Redis获取到 {len(processes)} 个已注册进程")
            return processes
            
        except Exception as e:
            log.error(f"获取Redis已注册进程列表失败: {e}", exc_info=True)
            return {}
    
    def extract_hostname_from_celery_worker(self, celery_worker_name: str) -> Optional[str]:
        """
        从Celery worker名称中提取hostname
        
        解析Celery worker名称格式，提取@符号后面的hostname部分。
        
        Args:
            celery_worker_name: Celery worker名称，格式为 "worker_name@hostname"
        
        Returns:
            Optional[str]: hostname部分，如果格式不正确（没有@符号）返回None
        """
        if "@" in celery_worker_name:
            return celery_worker_name.split("@", 1)[1]
        return None
    
    def extract_env_from_worker_name(self, worker_name: str) -> Optional[str]:
        """
        从worker名称中提取环境标识
        
        支持的格式：
        - celery_local@hostname -> local
        - celery_test@hostname -> test
        - celery_prod@hostname -> prod
        - worker_name_local@hostname -> local
        
        通过检查worker名称中是否包含常见环境标识后缀（_local、_test、_prod等）来提取环境。
        
        Args:
            worker_name: Worker名称，格式为 "worker_name_env@hostname" 或 "worker_name@hostname"
        
        Returns:
            Optional[str]: 环境标识（如 "local", "test", "prod"），如果未找到返回None
        """
        # 常见环境标识列表
        env_patterns = ['_local', '_test', '_prod', '_dev', '_staging']
        
        # 提取@之前的部分
        if "@" in worker_name:
            name_part = worker_name.split("@")[0]
        else:
            name_part = worker_name
        
        # 检查是否包含环境标识
        for pattern in env_patterns:
            if name_part.endswith(pattern):
                return pattern[1:]  # 去掉下划线
        
        return None
    
    def is_same_env(self, worker_name: str) -> bool:
        """
        判断worker是否属于当前环境
        
        从worker名称中提取环境标识，与当前环境进行比较。
        如果worker名称中没有环境标识，将返回False（不再向后兼容）。
        
        Args:
            worker_name: Worker名称（Celery格式或Redis格式），如 "celery_local@hostname"
        
        Returns:
            bool: 如果worker属于当前环境返回True，否则返回False
        
        Note:
            Worker名称必须明确包含环境标识（如 _local, _test, _prod 等），
            如果没有环境标识，将返回False，拒绝该worker。
        """
        # 从worker名称提取环境
        worker_env = self.extract_env_from_worker_name(worker_name)
        
        # 如果worker名称中没有环境标识，拒绝该worker（不再向后兼容）
        if worker_env is None:
            return False
        
        # 比较环境是否匹配
        return worker_env == self.current_env
    
    def is_local_worker(self, worker_name: str) -> bool:
        """
        判断worker是否在当前机器上
        
        从worker名称中提取hostname，与当前机器的主机名进行比较。
        
        Args:
            worker_name: worker名称，可以是：
                - 完整格式: "celery_local@hostname"
                - 仅hostname: "hostname"
        
        Returns:
            bool: 如果是本地worker返回True，否则返回False
        """
        # 提取 hostname 部分进行比较
        hostname = extract_hostname_from_worker_name(worker_name)
        if hostname is None:
            # worker_name 不包含 @，本身就是 hostname
            hostname = worker_name
        
        return hostname == self.local_hostname
    
    def check_process_exists(self, pid: int) -> bool:
        """
        检查进程是否真的存在（仅适用于本地进程）
        
        使用os.kill(pid, 0)检查进程是否存在。如果进程不存在会抛出OSError异常。
        注意：此方法只能检查本地机器上的进程，无法检查远程机器上的进程。
        
        Args:
            pid: 进程ID，用于检查的进程标识符
        
        Returns:
            bool: 如果进程存在返回True，否则返回False
        """
        try:
            # 使用os.kill(pid, 0)检查进程是否存在
            # 如果进程不存在，会抛出OSError
            # 注意：os.kill只能检查本地机器上的进程
            os.kill(pid, 0)
            return True
        except OSError:
            # 进程不存在
            return False
        except Exception as e:
            log.warning(f"检查进程存在性时出错: pid={pid}, error={e}")
            return False
    
    def match_worker_name(self, celery_worker_name: str, redis_worker_name: str) -> Tuple[bool, Optional[str]]:
        """
        匹配Celery worker名称和Redis中的worker名称，并返回hostname
        
        直接比较两个worker名称是否完全相同。Redis中存储的worker_name实际上是
        完整的Celery worker名称（来自self.request.hostname）。
        
        Celery worker名称格式: "worker_name@hostname"
        Redis worker名称格式: "worker_name@hostname" (完整的Celery worker名称)
        
        Args:
            celery_worker_name: Celery worker名称（如 "celery_local@hostname"）
            redis_worker_name: Redis中的worker名称（完整Celery worker名称，如 "celery_local@hostname"）
        
        Returns:
            Tuple[bool, Optional[str]]: (是否匹配, hostname)，如果匹配返回True和hostname，否则返回False和None
        """
        # 直接比较完整的worker名称
        # Redis中存储的worker_name实际上是完整的Celery worker名称（来自self.request.hostname）
        is_match = celery_worker_name == redis_worker_name
        
        # 提取hostname用于返回
        hostname = extract_hostname_from_worker_name(celery_worker_name)
        
        return (is_match, hostname)
    
    def check_workers(self) -> Dict[str, Any]:
        """
        检查worker状态，返回检查结果
        
        通过对比Celery活跃worker列表和Redis中注册的进程，找出已消失的worker。
        同时检查worker数量是否满足最小健康要求。
        
        检查流程：
        1. 获取Celery中的活跃worker（已过滤当前环境）
        2. 获取Redis中注册的进程（已过滤当前环境）
        3. 验证每个Redis进程是否在Celery活跃列表中
        4. 对于本地worker，使用os.kill验证进程是否真的存在
        5. 统计活跃worker数量和已消失worker列表
        6. 检查是否满足最小健康worker数量要求
        
        Returns:
            Dict[str, Any]: 检查结果字典，包含：
                - active_worker_count: 活跃worker数量
                - missing_workers: 已消失的worker列表，每个元素包含worker_name、pid、current_task等信息
                - healthy: 是否健康（数量是否满足要求）
                - checked_processes: 已检查的进程列表（用于调试）
        """
        result = {
            "active_worker_count": 0,
            "missing_workers": [],
            "healthy": False,
            "checked_processes": []
        }
        
        try:
            # 1. 获取Celery中的活跃worker（已经过滤了当前环境的worker）
            celery_workers = self.get_active_workers_from_celery()
            
            # 2. 获取Redis中注册的进程
            redis_processes = self.get_registered_processes_from_redis()
            
            # 过滤出当前环境的Redis进程
            # 注意：Redis中存储的worker_name是完整的Celery worker名称（如 celery_local@hostname）
            # 我们可以直接从worker_name提取环境信息
            filtered_redis_processes = {}
            redis_filtered_out_count = 0
            
            # 建立hostname到Celery worker的映射（用于环境判断）
            hostname_to_celery_worker = {}
            for celery_worker_name in celery_workers:
                hostname = extract_hostname_from_worker_name(celery_worker_name)
                if hostname:
                    hostname_to_celery_worker[hostname] = celery_worker_name
            
            for process_str, process_status in redis_processes.items():
                worker_name = process_status.get("worker_name")  # 完整的Celery worker名称
                
                # 查找对应的Celery worker来判断环境
                matched_celery_worker = hostname_to_celery_worker.get(worker_name)
                if matched_celery_worker and is_same_env(matched_celery_worker, self.current_env):
                    # 有匹配的Celery worker且环境匹配
                    filtered_redis_processes[process_str] = process_status
                elif matched_celery_worker:
                    # 有匹配的Celery worker但环境不匹配
                    redis_filtered_out_count += 1
                    log.debug(f"过滤掉不同环境的Redis进程: {worker_name} (当前环境: {self.current_env})")
                else:
                    # 没有匹配的Celery worker，可能是旧数据或不同环境的worker
                    # 为了向后兼容，如果worker_name本身包含环境信息，也检查
                    if is_same_env(worker_name, self.current_env):
                        filtered_redis_processes[process_str] = process_status
                    else:
                        redis_filtered_out_count += 1
                        log.debug(f"过滤掉不同环境的Redis进程: {worker_name} (当前环境: {self.current_env})")
            
            redis_processes = filtered_redis_processes
            if redis_filtered_out_count > 0:
                log.info(f"环境过滤: 从Redis注册进程中过滤掉 {redis_filtered_out_count} 个不同环境的进程")
            
            # 3. 验证每个Redis进程
            valid_workers = set()
            missing_workers = []
            
            for process_str, process_status in redis_processes.items():
                worker_name = process_status.get("worker_name")  # 完整的Celery worker名称
                pid = process_status.get("pid")
                
                # 查找对应的Celery worker
                matched_celery_worker = None
                for celery_worker_name in celery_workers:
                    is_match, hostname = self.match_worker_name(celery_worker_name, worker_name)
                    if is_match:
                        matched_celery_worker = celery_worker_name
                        break
                
                # 检查进程是否真的存在（仅对本地worker）
                is_local = self.is_local_worker(worker_name)
                process_exists = True  # 默认认为存在
                
                if is_local:
                    # 本地worker：使用os.kill检查进程是否存在
                    process_exists = self.check_process_exists(pid)
                    result["checked_processes"].append({
                        "worker_name": worker_name,
                        "pid": pid,
                        "hostname": worker_name,
                        "is_local": True,
                        "process_exists": process_exists
                    })
                else:
                    # 远程worker：只依赖Celery inspect API
                    # 如果Celery显示worker活跃，就认为进程存在
                    process_exists = matched_celery_worker is not None
                    result["checked_processes"].append({
                        "worker_name": worker_name,
                        "pid": pid,
                        "hostname": worker_name,
                        "is_local": False,
                        "process_exists": process_exists,
                        "note": "远程worker，依赖Celery inspect API判断"
                    })
                
                if not process_exists:
                    # 进程不存在，标记为丢失
                    log.warning(f"检测到进程不存在: {worker_name}:{pid} (本地={is_local})")
                    missing_workers.append({
                        "worker_name": worker_name,
                        "pid": pid,
                        "process_str": process_str,
                        "current_task": process_status.get("current_task"),
                        "reason": "进程不存在" if is_local else "不在Celery活跃列表中",
                        "is_local": is_local
                    })
                    continue
                
                # 检查是否在Celery活跃worker列表中
                if matched_celery_worker:
                    valid_workers.add(matched_celery_worker)
                else:
                    # Redis中有但Celery中没有，可能是worker已断开连接
                    log.warning(f"检测到worker不在Celery活跃列表中: {worker_name}:{pid}")
                    missing_workers.append({
                        "worker_name": worker_name,
                        "pid": pid,
                        "process_str": process_str,
                        "current_task": process_status.get("current_task"),
                        "reason": "不在Celery活跃列表中",
                        "is_local": is_local
                    })
            
            # 4. 统计活跃worker数量（使用Celery中的活跃worker数量）
            result["active_worker_count"] = len(celery_workers)
            result["missing_workers"] = missing_workers
            
            # 5. 检查是否满足最小健康worker数量要求
            result["healthy"] = result["active_worker_count"] >= self.min_healthy_workers
            
            if not result["healthy"]:
                log.error(
                    f"Worker数量不足: 当前={result['active_worker_count']}, "
                    f"最小要求={self.min_healthy_workers}"
                )
            
            log.info(
                f"Worker检查完成: 活跃={result['active_worker_count']}, "
                f"丢失={len(missing_workers)}, 健康={result['healthy']}, "
                f"本地主机={self.local_hostname}, 当前环境={self.current_env}"
            )
            
        except Exception as e:
            log.error(f"检查worker状态时出错: {e}", exc_info=True)
            result["error"] = str(e)
        
        return result
    
    def cleanup_missing_workers(self, missing_workers: List[Dict[str, Any]]) -> int:
        """
        清理已消失worker的Redis记录
        
        遍历已消失的worker列表，清理每个worker在Redis中的所有进程信息。
        如果worker有正在执行的任务，会在missing_worker字典中标记needs_recovery=True，
        由调用者处理任务恢复。
        
        Args:
            missing_workers: 已消失的worker列表，每个元素包含worker_name、pid、current_task等信息
        
        Returns:
            int: 成功清理的worker数量
        """
        cleaned_count = 0
        
        for missing_worker in missing_workers:
            worker_name = missing_worker.get("worker_name")
            pid = missing_worker.get("pid")
            current_task_id = missing_worker.get("current_task")
            
            try:
                log.info(
                    f"清理已消失worker的Redis记录: {worker_name}:{pid}, "
                    f"原因={missing_worker.get('reason')}"
                )
                
                # 清理进程信息
                process_health_monitor.cleanup_process(worker_name, pid)
                cleaned_count += 1
                
                # 如果有正在执行的任务，需要恢复任务状态
                if current_task_id:
                    log.warning(
                        f"已消失worker有正在执行的任务，需要恢复: "
                        f"worker={worker_name}:{pid}, task_id={current_task_id}"
                    )
                    # 返回任务ID，由调用者处理任务恢复
                    missing_worker["needs_recovery"] = True
                
            except Exception as e:
                log.error(
                    f"清理worker记录失败: {worker_name}:{pid}, error={e}",
                    exc_info=True
                )
        
        return cleaned_count

