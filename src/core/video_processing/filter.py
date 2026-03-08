from models.pydantic_models.request.filter_config import FILTER_TEMPLATES
from utils.log_utils import logger as log

FILTER_HANDLERS = {
    "temperature": lambda
        cfg: f"colorbalance=rs={cfg.value / 500 * 1.5}:rm={cfg.value / 500 * 1.5}:rh={cfg.value / 500 * 1.5}:bs={-cfg.value / 500 * 1.5}:bm={-cfg.value / 500 * 1.5}:bh={-cfg.value / 500 * 1.5}",
    "brightness": lambda cfg: f"eq=brightness={cfg.value}",
    "tint": lambda
        cfg: f"colorbalance=rs={cfg.value / 500 * 1.5}:gs={-cfg.value / 500 * 1.5}:bs={cfg.value / 500 * 1.5}:"
             f"rm={cfg.value / 500 * 1.5}:gm={-cfg.value / 500 * 1.5}:bm={cfg.value / 500 * 1.5}:"
             f"rh={cfg.value / 500 * 1.5}:gh={-cfg.value / 500 * 1.5}:bh={cfg.value / 500 * 1.5}",
    "contrast": lambda cfg: f"eq=contrast={cfg.value * 2}",
    "saturation": lambda cfg: f"eq=saturation={cfg.value}",
    "hue": lambda cfg: f"hue=h={cfg.value}",
    "sharpness": lambda cfg: f"unsharp=luma_msize_x=5:luma_msize_y=5:luma_amount={cfg.value * 2}",
    "boxblur": lambda cfg: f"boxblur={cfg.value}",
    "gblur": lambda cfg: f"gblur=sigma={cfg.value}",
    "dblur": lambda cfg: f"dblur=angle={cfg.angle}:radius={cfg.value}",
}



def build_from_config(filter_config, templates=FILTER_TEMPLATES):
    """
    根据配置构建滤镜字符串

    Args:
        filter_config: 滤镜配置对象
        templates: 额外的滤镜字典

    Returns:
        滤镜字符串，多个滤镜用逗号分隔
    """
    if not filter_config:
        return ""


    filter_list = []

    # 1. 添加模板滤镜
    if filter_config.filter_template and filter_config.filter_template in templates:
        filter_list.append(templates[filter_config.filter_template])

    # 2. 添加配置的滤镜
    if filter_config.filter_configs:
        filter_list.extend(_build_filters(filter_config.filter_configs))

    return ",".join(filter_list) if filter_list else ""


def _build_filters(filter_configs):
    """构建单个滤镜列表"""
    filters = []
    for cfg in filter_configs:
        if cfg.type in FILTER_HANDLERS:
            try:
                filters.append(FILTER_HANDLERS[cfg.type](cfg))
            except (AttributeError, TypeError, ValueError) as e:
                log.warning(f"构建滤镜 {cfg.type} 失败: {e}")
                continue
    return filters

