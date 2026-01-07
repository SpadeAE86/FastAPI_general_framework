import uvicorn, asyncio, concurrent, os, json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from api import *
from utils.log_utils import logger as log
from utils.obs_utils import *
from config.config import *
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
from exceptions.ServiceException import ServiceException
from database import *
from celery_mq import *
from core.health_monitor import start_health_monitor, stop_health_monitor


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("FastAPI started")
    log.info("inject main loop")
    loop = asyncio.get_running_loop()
    await asyncio.to_thread(lambda: None)
    default_pool = getattr(loop, "_default_executor", None)

    if default_pool:
        pool_size = getattr(default_pool, "_max_workers", "Unknown")
        log.info(f"当前默认线程池大小 (Max Workers): {pool_size}")

    else:
        log.info("无法获取默认线程池")

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=100)
    loop.set_default_executor(executor)
    log.info("Default thread pool executor set to max_workers=100")
    memory.inject_fastapi_loop(loop)
    if my_config["env"] == "local" and os.path.exists("memory.json"):
        with open("memory.json") as f:
            data = json.load(f)
        memory.load_memory(data)
    log.info("memory loaded")
    log.info(f"established {len(db_manager.engines)} connections to mysql database")
    
    # 启动健康监控服务
    start_health_monitor()
    
    try:
        yield
    finally:
        # 停止健康监控服务
        stop_health_monitor()
        log.info("shutting down...")
        log.info("exit")

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in all_router:
    app.include_router(r)

# 全局兜底异常处理
@app.exception_handler(ServiceException)
async def business_exception_handler(request: Request, exc: ServiceException):
    log.info(f"[Service Exception] {exc.code}: {exc.message}, extra info: {exc.data}")
    return JSONResponse(
        status_code=200,  # 可以统一返回 200，code 自定义区分错误类型
        content={
            "code": exc.code,
            "message": exc.message,
            "data": exc.data,
        },
    )

if __name__ == "__main__":
    uvicorn.run("FastAPI_server:app", host="0.0.0.0", port=8001)
