# FastAPI_server.py — 统一服务入口
# 职责:
#   1. 初始化 FastAPI 应用实例
#   2. 注册所有 routers (chat, agent, memory, task)
#   3. 挂载中间件 (CORS, 日志, 异常处理)
#   4. 启动时初始化 infra 层 (scheduler, mq, cache)
#   5. 关闭时优雅释放资源
import uvicorn, asyncio, os, json, contextlib
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from routers import *
from infra.logging.logger import logger as log
from services.analysis_video import start_embedding_warmup_background
# from utils.obs_utils import *

from config.config import *
from contextlib import asynccontextmanager
from exceptions.infra import ServiceException
# init connectors and tables
from infra.connector_loader import connector_loader
from infra.storage.sqlmodel_init import create_tables_if_not_exists
# from database import *
# from core.health_monitor.lifespan import start_health_monitor, stop_health_monitor


@asynccontextmanager
async def lifespan(app: FastAPI):
    warmup_task: asyncio.Task[None] | None = None
    # --- 环境预设 ---
    # 使用国内 HF 镜像加速模型下载
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
    # 开启加速下载
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

    log.info("FastAPI started")
    # 不要用 loop.set_default_executor 替换 Uvicorn/asyncio 的默认线程池：
    # 在 Windows 上曾出现「Application startup complete 后仍像完全收不到 HTTP」的现象，
    # 可能与默认执行器被替换后部分 IO/回调无法调度有关。向量模型改由独立池加载（见 analysis_video._EMBED_EXECUTOR）。

    try:
        # Initialize infra connectors (mysql/redis/rabbitmq/opensearch)
        await connector_loader.startup()
        # Create SQLModel tables if missing
        await create_tables_if_not_exists()

        try:
            from services.interrupted_tasks_recovery import mark_interrupted_tasks_on_startup

            await mark_interrupted_tasks_on_startup("服务重启或进程中断，任务未完成")
        except Exception as _e:
            log.warning("启动时标记中断任务失败（可忽略若表未就绪）: %s", _e)

        if os.environ.get("SKIP_FRAME_ORIENTATION_BACKFILL", "").strip().lower() in (
            "1",
            "true",
            "yes",
        ):
            log.info("已设置 SKIP_FRAME_ORIENTATION_BACKFILL，跳过 frame_orientation 索引回填")
        else:

            async def _frame_orientation_backfill_bg() -> None:
                try:
                    await asyncio.sleep(2)
                    from services.frame_orientation_os_backfill import run_frame_orientation_backfill

                    n = await run_frame_orientation_backfill()
                    log.info("OpenSearch frame_orientation 回填完成，更新文档数: %s", n)
                except Exception as _fo:
                    log.warning(
                        "frame_orientation 回填未执行或失败（可稍后手动: python -m services.frame_orientation_os_backfill）: %s",
                        _fo,
                    )

            asyncio.create_task(_frame_orientation_backfill_bg())

        # 模型预热（后台 task，不 await）：yield 后 HTTP 立即可用；OpenSearch 入库前会 await ensure_embedding_model_ready 等待同一加载任务。
        warmup_task = start_embedding_warmup_background()
        log.info("已向后台派发向量模型预热；HTTP 即将就绪（向量化入库前会等待预热完成）。")
        yield
    finally:
        if warmup_task is not None and not warmup_task.done():
            warmup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await warmup_task
        # 停止健康监控服务
        try:
            await connector_loader.shutdown()
        except Exception as e:
            log.warning(f"connector shutdown failed: {e}")
        try:
            from infra.storage.mix_overall_time_mysql import dispose_mix_overall_time_engine

            await dispose_mix_overall_time_engine()
        except Exception:
            pass
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

@app.get("/health")
async def health_check():
    return {"status": "ok"}

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
