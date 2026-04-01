"""
文件工具
"""

import yaml
from pathlib import Path
from typing import Union


def get_project_root() -> Path:
    """
    获取项目根目录（向上查找 src）
    :return:
    """
    current_path = Path(__file__).resolve()
    while current_path.parent != current_path:
        if (current_path / 'src').exists():
            return current_path
        current_path = current_path.parent
    raise FileNotFoundError


def read_yaml(file: Union[Path, str]) -> dict:
    """
    读取 yaml 文件
    :param file:
    :return:
    """
    with open(file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save_yaml(file: Union[Path, str], data: dict):
    """
    保存 yaml 文件
    :param file:
    :param data:
    :return:
    """
    with open(file, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True)


if __name__ == '__main__':
    # ----------------------------------------------------
    # 测试
    # ----------------------------------------------------

    # 测试获取项目根目录
    print(f'{get_project_root() = }')

    # 测试读、写配置文件
    from config.config import CONFIG_FILE

    _my_config = read_yaml(CONFIG_FILE)
    print(f'{_my_config = }')

    # 测试写配置文件
    import time
    from config.config import TEMP_DIR

    save_yaml(TEMP_DIR / f'测试配置{time.time()}.yml', _my_config)
