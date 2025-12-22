import httpx, asyncio
from utils.log_utils import logger as log

async def post(host, resp_vo, retry = 4, task_id = "test", headers = None):
    result = None
    if headers is None:
        headers = {}
    async with httpx.AsyncClient() as client:
        for i in range(retry):
            msg = await client.post(host, json=resp_vo, headers=headers,  # 添加 headers 参数
                                    timeout=60.0)
            if msg.status_code == 200:
                log.info(f"回调成功, msg: {msg.json()}")
                result = msg.json()
                break
            log.info(f"第{i}次回调失败，10秒后重试")
            await asyncio.sleep(10)
        log.info(f"{task_id}处理完成")
    return result

async def get(host, params=None, retry=4, task_id="test", headers=None):
    if headers is None:
        headers = {}
    if params is None:
        params = {}

    async with httpx.AsyncClient() as client:
        for i in range(retry):
            try:
                msg = await client.get(host, params=params, headers=headers, timeout=10.0)
                if msg.status_code == 200:
                    log.info(f"GET请求成功, msg: {msg.json()}")
                    return msg.json()  # 返回响应数据
                log.info(f"第{i + 1}次GET请求失败，状态码: {msg.status_code}, 10秒后重试")
            except httpx.TimeoutException:
                log.info(f"第{i + 1}次GET请求超时，10秒后重试")
            except httpx.RequestError as e:
                log.info(f"第{i + 1}次GET请求错误: {str(e)}，10秒后重试")
            except Exception as e:
                log.info(f"第{i + 1}次GET请求发生异常: {str(e)}，10秒后重试")

            await asyncio.sleep(10)
        log.info(f"{task_id} GET请求处理完成")
        return None  # 所有重试都失败后返回None_vo, retry = 4, task_id = "test", headers = None):