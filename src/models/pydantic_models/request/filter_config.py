from pydantic import BaseModel, Field
from typing import *

filter_options = ["temperature", "tint", "hue", "saturation", "brightness", "contrast", "sharpness", "gamma", "boxblur",
                  "gblur", "dblur"]

FILTER_TEMPLATES = {
    # 1. 自然光
    "natural_light": "eq=brightness=0.06:saturation=1.1:gamma=1.05",
    # 2. 柔和
    "soft": "boxblur=luma_radius=0.8:luma_power=1,eq=contrast=0.95:saturation=1.05",
    # 3. 赤褐
    "sepia": "curves=r='0/0 0.4/0.5 1/0.9':g='0/0 0.5/0.45 1/0.8':b='0/0 0.6/0.35 1/0.7'",
    # 4. 质感
    "texture": "unsharp=5:5:1.5,eq=contrast=1.15:gamma=0.95",
    # 5. 暖阳
    "warm_sun": "colorbalance=rs=0.15:gs=-0.05:bs=-0.1,eq=gamma=1.1:brightness=0.08",
    # 6. 美餐
    "delicious": "hue=h=-10:s=1.3,eq=contrast=1.1:brightness=0.05",
    # 7. 入味
    "vintage_taste": "curves=preset=vintage,eq=saturation=1.25:gamma=1.15",
    # 8. 可口
    "tasty": "eq=contrast=1.2:saturation=1.4:gamma=0.98,colorbalance=rm=0.1:bm=-0.1",
    # 9. 太妃糖
    "toffee": "curves=r='0/0 0.3/0.4 0.7/0.8 1/0.9':g='0/0 0.4/0.3 1/0.7':b='0/0 0.5/0.2 1/0.6'",
    # 10. 晶亮
    "crystal": "unsharp=7:7:2.5,eq=contrast=1.25:gamma=1.2:brightness=0.03",
    # 11. 明媚
    "bright": "eq=brightness=0.15:saturation=1.35:contrast=1.1",
    # 12. 蓝调
    "blue_tone": "eq=contrast=1.1:saturation=1.3:brightness=0.05,hue=h=10",
    # "colorbalance=rs=-0.2:gs=-0.1:bs=0.3,eq=gamma=0.9",
    # 13. 胶片
    "film": "curves=strong_contrast,noise=alls=25:allf=t,eq=gamma=0.95",
    # 14. 拍立得
    "polaroid": "curves=r='0/0.1 0.5/0.6 1/0.9':g='0/0.1 0.5/0.55 1/0.85':b='0/0.1 0.5/0.5 1/0.8',vignette",
    # 15. 黑白
    "blackwhite": "hue=s=0",
    # 16. 灰调
    "gray_tone": "hue=s=0,curves=r='0/0 0.3/0.4 0.7/0.6 1/0.8':g='0/0 0.3/0.4 0.7/0.6 1/0.8':b='0/0 0.3/0.4 0.7/0.6 1/0.8'"
}

# 单个视频的滤镜调色
class FilterConfig(BaseModel):
    type: Literal[*filter_options] = "saturation"
    # 色调
    value: float = Field(default=0)
    angle: float = Field(default=0)

# 视频滤镜调色列表
class VideoFilterConfig(BaseModel):
    filter_configs: List[Optional[FilterConfig]] = Field(default_factory=lambda: [])
    filter_template: Optional[Literal[*list(FILTER_TEMPLATES.keys())]] = None
