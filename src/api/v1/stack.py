import os.path
import subprocess
import sys
import threading
import traceback

import psutil
from fastapi import APIRouter
from tabulate import tabulate

from utils.log_utils import logger as log

stack_router = APIRouter()


def get_cpu_usage():
    """获取 CPU 整体及各核心利用率"""
    return {
        "cpu_percent_total": f"{psutil.cpu_percent(interval=0.2)}%",
        "cpu_percent_per_core": [f"{p}%" for p in psutil.cpu_percent(interval=0, percpu=True)],
        "cpu_count": psutil.cpu_count(logical=True),
    }


def get_gpu_usage():
    """获取 NVIDIA GPU 状态，包括显存占用和显卡利用率"""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total,encoder.stats.sessionCount,decoder.stats.sessionCount",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        gpus = []
        for line in result.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            gpus.append({
                "index": parts[0],
                "name": parts[1],
                "gpu_util": parts[2] + "%",
                "mem_util": parts[3] + "%",
                "mem_used": parts[4] + "MB",
                "mem_total": parts[5] + "MB",
                "encoder_sessions": parts[6],
                "decoder_sessions": parts[7],
            })
        return gpus
    except FileNotFoundError:
        return {"error": "nvidia-smi not found（非 NVIDIA 环境或驱动未安装）"}
    except Exception as e:
        return {"error": str(e)}


@stack_router.get("/stack")
async def debug_stack():
    """调试接口：打印所有线程调用栈、CPU 利用率和 GPU 状态"""
    # ------ 线程调用栈 ------
    stacks = []
    for thread_id, frame in sys._current_frames().items():
        stacks.append(f"Thread {thread_id}:\n{''.join(traceback.format_stack(frame))}")

    headers = ["ThreadID", "Name", "State", "Key Stack Point"]
    rows = []
    for tid, frame in sys._current_frames().items():
        stack = traceback.extract_stack(frame)
        last_call = stack[-1] if stack else None
        row = [
            tid,
            next((t.name for t in threading.enumerate() if t.ident == tid), "Unknown"),
            "阻塞" if last_call and "ssl.py" in last_call.filename else "运行",
            f"{os.path.basename(last_call.filename)}:{last_call.lineno}" if last_call else "",
        ]
        rows.append(row)

    log.info(tabulate(rows, headers=headers))

    # ------ CPU ------
    cpu_info = get_cpu_usage()
    log.info(f"[CPU] 总体: {cpu_info['cpu_percent_total']}  各核: {cpu_info['cpu_percent_per_core']}")

    # ------ GPU ------
    gpu_info = get_gpu_usage()
    log.info(f"[GPU] {gpu_info}")

    return {
        "stacks": stacks,
        "cpu": cpu_info,
        "gpu": gpu_info,
    }
