"""
华为云 CES (Cloud Eye Service) API 客户端
用于上报自定义监控指标数据
"""
import asyncio
from typing import List, Dict, Any, Optional
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkces.v1.region.ces_region import CesRegion
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkces.v1 import *
from config.config import my_config, ENV
from utils.log_utils import logger as log


class CESClient:
    """华为云 CES API 客户端"""
    
    def __init__(self, access_key: str, secret_key: str, project_id: str, region: str = "cn-east-3"):
        """
        初始化 CES 客户端
        
        Args:
            access_key: 华为云访问密钥 AK
            secret_key: 华为云访问密钥 SK
            project_id: 项目ID
            region: 区域，默认为 cn-east-3
        """
        self.access_key = access_key
        self.secret_key = secret_key
        self.project_id = project_id
        self.region = region
        self.endpoint = f"https://ces.{region}.myhuaweicloud.com"
        self.base_url = f"{self.endpoint}/V1.0/{project_id}"
        
        # 使用官方 SDK 创建客户端
        credentials = BasicCredentials(access_key, secret_key)
        self.client = CesClient.new_builder() \
            .with_credentials(credentials) \
            .with_region(CesRegion.value_of(region)) \
            .build()
    
    async def create_metric_data(self, metric_data: List[Dict[str, Any]]) -> bool:
        """
        创建监控指标数据（异步接口）
        
        Args:
            metric_data: 监控指标数据列表，格式如下：
                [{
                    "metric": {
                        "namespace": "MINE.APP",
                        "metric_name": "rabbitmq_queue_length",
                        "dimensions": [{
                            "name": "queue_name",
                            "value": "video_queue"
                        }]
                    },
                    "ttl": 604800,
                    "collect_time": 1609459200000,
                    "value": 100,
                    "unit": "count"
                }]
        
        Returns:
            成功返回 True，失败返回 False
        """
        if not metric_data:
            log.warning("监控指标数据为空，跳过上报")
            return False
        
        try:
            # 将字典格式转换为 SDK 对象格式
            list_bodybody = []
            for item in metric_data:
                metric_dict = item.get("metric", {})
                dimensions = metric_dict.get("dimensions", [])
                
                # 构建维度列表
                list_dimensions_metric = []
                for dim in dimensions:
                    list_dimensions_metric.append(
                        MetricsDimension(
                            name=dim.get("name"),
                            value=dim.get("value")
                        )
                    )
                
                # 构建指标信息
                metric_body = MetricInfo(
                    namespace=metric_dict.get("namespace"),
                    metric_name=metric_dict.get("metric_name"),
                    dimensions=list_dimensions_metric
                )
                
                # 构建请求体，支持 collect_time 和 value 字段
                request_body_kwargs = {
                    "metric": metric_body,
                    "ttl": item.get("ttl", 3600)
                }
                
                # 如果提供了 collect_time，添加到请求体中
                if "collect_time" in item:
                    request_body_kwargs["collect_time"] = item.get("collect_time")
                
                # 如果提供了 value，添加到请求体中
                if "value" in item:
                    request_body_kwargs["value"] = item.get("value")
                
                # 如果提供了 unit，添加到请求体中（如果 SDK 支持）
                if "unit" in item:
                    # unit 字段可能不在 CreateMetricDataRequestBody 中，先尝试
                    try:
                        request_body_kwargs["unit"] = item.get("unit")
                    except:
                        pass  # 如果 SDK 不支持 unit 字段，忽略
                
                request_body = CreateMetricDataRequestBody(**request_body_kwargs)
                list_bodybody.append(request_body)
            
            # 创建请求
            request = CreateMetricDataRequest()
            request.body = list_bodybody
            
            # 使用 asyncio.to_thread 在线程池中执行阻塞的 SDK 调用
            response = await asyncio.to_thread(self.client.create_metric_data, request)
            log.debug(f"成功上报监控数据: {len(metric_data)} 条指标")
            return True
            
        except exceptions.ClientRequestException as e:
            log.error(
                f"上报监控数据失败: 状态码={e.status_code}, "
                f"错误码={e.error_code}, "
                f"错误信息={e.error_msg}, "
                f"请求ID={e.request_id}"
            )
            return False
        except Exception as e:
            log.error(f"上报监控数据时发生未知错误: {e}", exc_info=True)
            return False


def get_ces_client() -> Optional[CESClient]:
    """
    从配置中获取 CES 客户端实例
    
    Returns:
        CESClient 实例，如果配置未启用或配置不完整则返回 None
    """
    try:
        ces_config = my_config.get("huawei_ces", {}).get(ENV, {})
        
        if not ces_config.get("enabled", False):
            return None
        
        access_key = os.getenv("HUAWEI_CES_AK")
        secret_key = os.getenv("HUAWEI_CES_SK")
        import os
        project_id = ces_config.get("project_id")
        region = ces_config.get("region", "cn-east-3")
        
        if not all([access_key, secret_key, project_id]):
            log.warning("华为云 CES 配置不完整，跳过初始化")
            return None
        
        return CESClient(access_key, secret_key, project_id, region)
        
    except Exception as e:
        log.error(f"初始化 CES 客户端失败: {e}", exc_info=True)
        return None
