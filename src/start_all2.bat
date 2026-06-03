@echo off
chcp 65001 >nul

echo ==============================
echo 启动 AIGC Video Mix Services
echo ==============================

REM 配置路径
set PROJECT_DIR=C:\Job\AI\mix\AIGC_video_mix_remake
set SRC_DIR=%PROJECT_DIR%\src
set CONDA_ENV=py312

REM 获取 conda 的安装路径 (通常在用户目录下)
set CONDA_PATH=%USERPROFILE%\.conda
set CONDA_ACTIVATE=%USERPROFILE%\miniconda3\Scripts\activate.bat

REM 尝试多个可能的 conda 路径
if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" (
    set CONDA_ACTIVATE=%USERPROFILE%\miniconda3\Scripts\activate.bat
) else if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" (
    set CONDA_ACTIVATE=%USERPROFILE%\anaconda3\Scripts\activate.bat
) else if exist "C:\ProgramData\miniconda3\Scripts\activate.bat" (
    set CONDA_ACTIVATE=C:\ProgramData\miniconda3\Scripts\activate.bat
) else if exist "C:\ProgramData\anaconda3\Scripts\activate.bat" (
    set CONDA_ACTIVATE=C:\ProgramData\anaconda3\Scripts\activate.bat
) else if exist "%USERPROFILE%\.conda\Scripts\activate.bat" (
    set CONDA_ACTIVATE=%USERPROFILE%\.conda\Scripts\activate.bat
)

echo 使用 Conda 激活脚本: %CONDA_ACTIVATE%
echo.

REM 1. 启动 FastAPI Server
echo [1/3] 启动 FastAPI Server...
start "FastAPI Server" cmd /k "call %CONDA_ACTIVATE% %CONDA_ENV% && cd /d %SRC_DIR% && uvicorn FastAPI_server:app --host 0.0.0.0 --port 8004 --reload"

timeout /t 3 >nul

REM 2. 启动 Dispatcher
echo [2/3] 启动 Dispatcher...
start "Dispatcher" cmd /k "call %CONDA_ACTIVATE% %CONDA_ENV% && cd /d %SRC_DIR% && python core\dispatcher\run.py"

timeout /t 3 >nul

REM 3. 启动 Celery Worker
echo [3/3] 启动 Celery Worker (Voice)...
start "Voice Celery Worker" cmd /k "call %CONDA_ACTIVATE% %CONDA_ENV% && cd /d %SRC_DIR% && python -m celery -A celery_mq.celery_app worker -P solo --hostname=celery_voice_local@%%h --loglevel=INFO --queues=local_voice_queue,local_volcovoice_queue --concurrency=1"
echo.
echo ==============================
echo 所有服务已启动！
echo ==============================
echo.
echo 启动的服务:
echo   - FastAPI Server (端口 8004)
echo   - Dispatcher (任务调度)
echo   - Celery Worker (local_voice_queue, local_volcovoice_queue)
echo.
echo 按任意键关闭此窗口...
pause >nul
