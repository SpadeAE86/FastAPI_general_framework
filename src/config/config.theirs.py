'''
项目配置
主要从 config.yml 中加载，其他写在当前 py 中
'''

import os
from pathlib import Path
from typing import Union

from utils.file_utils import get_project_root, read_yaml


def load_config(file: Union[Path, str]) -> dict:
    """
    加载配置文件
    :param file:
    :return:
    """
    return read_yaml(file)


# --- 项目根目录 ---
PROJECT_ROOT: Path = get_project_root()

# --- logs 目录 ---
LOGS_DIR: Path = PROJECT_ROOT / 'logs'

# --- src 目录 ---
SRC_DIR: Path = PROJECT_ROOT / 'src'

# --- static 目录 ---
STATIC_DIR: Path = PROJECT_ROOT / 'static'

# --- temp 目录 ---
TEMP_DIR: Path = PROJECT_ROOT / 'temp'
os.makedirs(TEMP_DIR, exist_ok=True)

# --- ffmpeg 目录 ---
FFMPEG_DIR: Path = STATIC_DIR / 'ffmpeg'
os.environ["PATH"] = str(FFMPEG_DIR) + os.pathsep + os.environ["PATH"]

# --- fonts 目录 ---
FONTS_DIR: Path = STATIC_DIR / 'fonts'
os.environ["PATH"] = str(FONTS_DIR) + os.pathsep + os.environ["PATH"]

# --- config 文件 ---
CONFIG_FILE: Path = SRC_DIR / 'config' / 'config.yml'

# --- 加载配置 ---
MY_CONFIG = load_config(CONFIG_FILE)

# --- 环境变量 ---
ENV = MY_CONFIG['env']

if __name__ == '__main__':
    # ----------------------------------------------------
    # 测试
    # ----------------------------------------------------

    # 测试加载配置文件
    print(f'{load_config(CONFIG_FILE) = }')
