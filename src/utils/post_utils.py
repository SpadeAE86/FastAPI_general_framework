import httpx, asyncio
from utils.log_utils import logger as log
from config.config import my_config

# 从配置读取 HTTP 请求参数
http_config = my_config.get("http", {})
post_config = http_config.get("post", {})
get_config = http_config.get("get", {})

# 默认值（如果配置不存在则使用这些值）
DEFAULT_POST_RETRY = post_config.get("retry", 4)
DEFAULT_POST_TIMEOUT = post_config.get("timeout", 60.0)
DEFAULT_POST_RETRY_SLEEP = post_config.get("retry_sleep", 10)
DEFAULT_GET_RETRY = get_config.get("retry", 4)
DEFAULT_GET_TIMEOUT = get_config.get("timeout", 10.0)
DEFAULT_GET_RETRY_SLEEP = get_config.get("retry_sleep", 10)

async def post(host, resp_vo, retry=None, task_id="test", headers=None):
    """
    POST 请求函数
    
    Args:
        host: 请求地址
        resp_vo: 请求体
        retry: 重试次数（None时使用配置值）
        task_id: 任务ID
        headers: 请求头
    """
    result = None
    if headers is None:
        headers = {}
    if retry is None:
        retry = DEFAULT_POST_RETRY
    
    async with httpx.AsyncClient() as client:
        for i in range(retry):
            msg = await client.post(host, json=resp_vo, headers=headers,
                                    timeout=DEFAULT_POST_TIMEOUT)
            if msg.status_code == 200:
                log.info(f"回调成功, msg: {msg.json()}")
                result = msg.json()
                break
            log.info(f"第{i}次回调失败，{DEFAULT_POST_RETRY_SLEEP}秒后重试")
            await asyncio.sleep(DEFAULT_POST_RETRY_SLEEP)
        log.info(f"{task_id}处理完成")
    return result

async def get(host, params=None, retry=None, task_id="test", headers=None):
    """
    GET 请求函数
    
    Args:
        host: 请求地址
        params: 请求参数
        retry: 重试次数（None时使用配置值）
        task_id: 任务ID
        headers: 请求头
    """
    if headers is None:
        headers = {}
    if params is None:
        params = {}
    if retry is None:
        retry = DEFAULT_GET_RETRY

    async with httpx.AsyncClient() as client:
        for i in range(retry):
            try:
                msg = await client.get(host, params=params, headers=headers, timeout=DEFAULT_GET_TIMEOUT)
                if msg.status_code == 200:
                    log.info(f"GET请求成功, msg: {msg.json()}")
                    return msg.json()  # 返回响应数据
                log.info(f"第{i + 1}次GET请求失败，状态码: {msg.status_code}, {DEFAULT_GET_RETRY_SLEEP}秒后重试")
            except httpx.TimeoutException:
                log.info(f"第{i + 1}次GET请求超时，{DEFAULT_GET_RETRY_SLEEP}秒后重试")
            except httpx.RequestError as e:
                log.info(f"第{i + 1}次GET请求错误: {str(e)}，{DEFAULT_GET_RETRY_SLEEP}秒后重试")
            except Exception as e:
                log.info(f"第{i + 1}次GET请求发生异常: {str(e)}，{DEFAULT_GET_RETRY_SLEEP}秒后重试")

            await asyncio.sleep(DEFAULT_GET_RETRY_SLEEP)
        log.info(f"{task_id} GET请求处理完成")
        return None  # 所有重试都失败后返回None