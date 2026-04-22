from dataclasses import dataclass
from typing import Literal, Optional

from PIL import Image, ImageDraw, ImageFont
import emoji, os
import logging
from utils.log_utils import logger as log

# 关闭 PIL/Pillow 的调试日志
logging.getLogger('PIL').setLevel(logging.WARNING)

f2f = {
    "Songti SC Regular": "Songti.ttc",
    "PingFang SC Regular": "PingFang.ttc",
    "Alibaba PuHuiTi": "Alibaba-PuHuiTi-Regular.ttf",
    "DengXian": "DengXian.ttf",
    "Heiti TC Medium": "STHeiti Medium.ttc",
    "Source Han Sans CN": "SourceHanSansCN-Regular#1.otf",
    "vivo Sans": "vivoSans-Regular.ttf",
    "MiSans": "MiSans-Regular.otf",
    "HONOR Sans CN": "HONORSansCN-Regular.ttf",
    "OPlusSans 3.0": "OPlusSans3-Regular.ttf",
    "HarmonyOS Sans SC": "HarmonyOS_Sans_SC_Regular.ttf",
    "PangMenZhengDao-Cu6.0": "庞门正道粗书体6.0.ttf",
    "Alibaba Health Font 2.0 CN 85 B": "AlibabaHealthFont2.0CN-85B.ttf",
    "baotuxiaobaiti": "包图小白体.ttf",
    "SJxingkai-C Regular": "三极行楷简体-粗.ttf",
    "YRDZST-Semibold": "杨任东竹石体-Semibold.ttf",
    "Slideqiuhong": "演示秋鸿楷.ttf",
    "TsangerShuYuanT W04": "仓耳舒圆体W04.ttf",
    "QTxiaotu": "千图小兔体.ttf",
    "Noto Color Emoji": "NotoColorEmoji-Regular.ttf",
    "Alimama ShuHeiTi Bold": "Alimama_ShuHeiTi_Bold.ttf",
    "Canger XiaoWanZi": "仓耳小丸子.ttf",
    "TsangerShuYuanT W01": "仓耳舒圆体W01.ttf",
    "YouShe Title Rounded": "优设标题圆.otf",
    "HXBNanShen 2.0": "胡晓波男神体2.0.otf",
    "HXBSaoBao 2.0": "胡晓波骚包体2.0.otf",
    "Alimama DaoLiTi Regular": "阿里妈妈刀隶体-Regular.ttf",
}

FONT_DIR = "./fonts"

@dataclass(frozen=True)
class Style:
    font_name: str
    font_size: int
    color: tuple
    outline_color: tuple
    outline_width: int

@dataclass
class Glyph:
    char: str | None
    style: Style | None
    width: float
    index: int
    control: str | None = None  # "LINE_BREAK"

def style_for_index(idx: int, base_style: Style, word_config):
    if not word_config:
        return base_style

    # 顺序扫描（cursor 会一直向前）
    for wc in word_config:
        if wc.start <= idx < wc.end:
            return Style(
                font_name = wc.font_type or base_style.font_name,
                font_size = wc.font_size or base_style.font_size,
                color = wc.color or base_style.color,
                outline_color = wc.outline_color or base_style.outline_color,
                outline_width = wc.outline_width or base_style.outline_width,
            )
    return base_style


emoji_dir="./google_emoji/128"  # 🔹 emoji 资源目录
def draw_text_with_outline(draw, text, x, y, font, font_color, outline_color, outline_width=2, letter_spacing=2):
    """
    在指定位置逐字绘制文字，支持描边和字距
    :param draw: PIL.ImageDraw.Draw 对象
    :param text: 要绘制的字符串
    :param x, y: 起始坐标
    :param font: PIL.ImageFont 对象
    :param font_color: 字体颜色 (r,g,b,a)
    :param outline_color: 描边颜色 (r,g,b,a)
    :param outline_width: 描边宽度
    :param letter_spacing: 字符间距，像素值
    """
    x_pos = x
    for ch in text:
        # 文字描边
        if outline_width > 0:
            for ox in range(-outline_width, outline_width + 1):
                for oy in range(-outline_width, outline_width + 1):
                    if ox == 0 and oy == 0:
                        continue
                    draw.text((x_pos + ox, y + oy), ch, font=font, fill=outline_color)

        # 文字本体
        draw.text((x_pos, y), ch, font=font, fill=font_color)

        # 前进坐标，加上字宽和字距
        char_width = draw.textlength(ch, font=font)
        x_pos += char_width + letter_spacing

    return x_pos  # 返回最后的 x 坐标，方便继续画



def create_subtitle_png(
    texts,
    font_name,
    anchor_x=960,
    anchor_y=540,
    font_size=40,
    font_color=(255, 255, 255, 255),
    outline_color=(0, 0, 0, 255),
    outline_width=2,
    line_spacing=10,
    background_style=0,  # 0 = 无背景，1 = 每行背景，2 = 整体背景
    background_color=(0, 0, 0, 128),  # 半透明黑色
    background_pad=10,
    png_width = 1920,
    png_height = 1080,
    save_path = "./fonts/test.png",
    scale = 1.0,
    rot = 0,
    letter_spacing = 4,
    word_config = None
):
    # 强制走 Skia GPU 版本（用于验证 Skia 绘制是否正常）
    try:
        from utils.draw_caption_utils_skia import create_subtitle_png as _skia_create_subtitle_png
        return _skia_create_subtitle_png(
            texts=texts,
            font_name=font_name,
            anchor_x=anchor_x,
            anchor_y=anchor_y,
            font_size=font_size,
            font_color=font_color,
            outline_color=outline_color,
            outline_width=outline_width,
            line_spacing=line_spacing,
            background_style=background_style,
            background_color=background_color,
            background_pad=background_pad,
            png_width=png_width,
            png_height=png_height,
            save_path=save_path,
            scale=scale,
            rot=rot,
            letter_spacing=letter_spacing,
            word_config=word_config,
        )
    except Exception:
        log.exception("Skia subtitle render failed")
        raise

    # NOTE: PIL 的实现代码保留在 git 历史中；当前分支用于验证 Skia 绘制，入口强制走 Skia。


# 示例
if __name__ == "__main__":
    # font_path = "baotuxiaobaiti"
    # # font_path = f"./fonts/{f2f["baotuxiaobaiti"]}"
    # img = create_subtitle_png(
    #     "这是第一行字幕\n这是第二行☺🫶☺🫶🫶☺🐬🔒🔮字幕",
    #     font_path,
    #     anchor_x=200,
    #     anchor_y=900,
    #     font_size=60,
    #     font_color=(255, 255, 0, 255),
    #     outline_color=(0, 0, 255, 255),
    #     outline_width=3,
    #     background_style=2,  # 改成 1 看每行背景
    #     background_color=(0, 0, 0, 0),
    #     background_pad=20,
    #     save_path="subtitle_final.png",
    #     scale = 0.5,
    #     rot=45,
    # )

    class Word:
        def __init__(
                self,
                start: int,
                end: int,
                font_size: Optional[int] = None,
                font_type: Optional[str] = None,
                color: Optional[str] = None,
                outline_color: Optional[str] = None,
                outline_width: Optional[int] = None,
        ):
            self.start = start
            self.end = end
            self.font_size = font_size
            self.font_type = font_type
            self.color = color
            self.outline_color = outline_color
            self.outline_width = outline_width


    word_config = [
        Word(
            start=3,  # 世
            end=5,  # 界（注意：end 是开区间）
            font_type="PangMenZhengDao-Cu6.0",
            font_size=80,
            color="#ff5050",
            outline_color="#000000",
            outline_width=6,
        )
    ]

    font_path = "Songti SC Regular"
    # font_path = f"./fonts/{f2f["baotuxiaobaiti"]}"
    img = create_subtitle_png(
        "一口沦陷！",
        font_path,
        anchor_x=960,
        anchor_y=900,
        font_size=60,
        font_color=(255, 255, 0, 255),
        outline_color=(0, 0, 255, 255),
        outline_width=3,
        png_width=640,
        png_height=360,
        background_style=2,  # 改成 1 看每行背景
        background_color=(85, 68, 136, 119),
        background_pad=20,
        save_path="subtitle_final.png",
        scale = 1,
        rot=0,
        word_config= None
    )