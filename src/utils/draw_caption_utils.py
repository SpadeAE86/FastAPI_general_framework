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
    png_height = 1280,
    save_path = "./fonts/test.png",
    scale = 1.0,
    rot = 0,
    letter_spacing = 4,
    word_config = None
):
    #第一步: 确定字体
    font_path = "/".join([FONT_DIR, f2f[font_name]])
    # print(f"font_path: {font_path}")
    font = ImageFont.truetype(font_path, font_size)
    img = Image.new("RGBA", (png_width, png_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    #第1.5步：生成字幕
    base_style = Style(
        font_name=font_name,
        font_size=font_size,
        color=font_color,
        outline_color=outline_color,
        outline_width=outline_width
    )
    max_line_width = png_width * 0.7
    glyph_lines: list[list[Glyph]] = []
    current_line: list[Glyph] = []
    global_idx = 0
    current_width = 0.0
    for raw_line in texts.split('\n'):

        for ch in raw_line:
            style = style_for_index(global_idx, base_style, word_config)

            # 字体实例（你可以加缓存）
            font_path = os.path.join(FONT_DIR, f2f[style.font_name])
            font_obj = ImageFont.truetype(font_path, style.font_size)

            # 量宽（这一步以后不会再算）
            width = draw.textlength(ch, font=font_obj) \
                    + letter_spacing \
                    + 2 * style.outline_width

            glyph = Glyph(
                char=ch,
                style=style,
                width=width,
                index=global_idx
            )

            # 🔹 自动换行判断
            if current_line and current_width + width > max_line_width:
                glyph_lines.append(current_line)
                current_line = []
                current_width = 0.0

            current_line.append(glyph)
            current_width += width
            global_idx += 1

        # 原文本里的换行：强制断行
        if current_line:
            glyph_lines.append(current_line)
            current_line = []
            current_width = 0.0
        # ⭐ newline 也占 index（与你现有语义一致）
        global_idx += 1

    log.info(f"constructed lines: {glyph_lines}")

    # ================================
    # 第二步：Glyph 行已经准备好
    # glyph_lines: List[List[Glyph]]
    # ================================
    lines = glyph_lines
    rows = len(lines)

    line_widths = []
    line_heights = []

    # ================================
    # 第三步：计算每一行的几何尺寸
    # ================================
    for line in lines:
        line_width = sum(g.width for g in line)

        line_height = max(
            (g.style.font_size + 2 * g.style.outline_width)
            for g in line
            if g.style is not None
        )

        line_widths.append(line_width)
        line_heights.append(line_height)

    # ================================
    # 第四步：整体文本垂直居中
    # ================================
    text_total_height = (
            sum(line_heights) +
            (rows - 1) * line_spacing
    )
    y = (png_height - text_total_height) / 2

    # ================================
    # 第五步：背景层绘制
    # ================================
    bg_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg_layer)

    if background_style == 2:
        total_width = max(line_widths)
        x0 = (png_width - total_width) / 2 - background_pad
        y0 = y - background_pad
        x1 = (png_width + total_width) / 2 + background_pad
        y1 = y + text_total_height + background_pad
        bg_draw.rectangle([x0, y0, x1, y1], fill=background_color)

    img = Image.alpha_composite(img, bg_layer)
    draw = ImageDraw.Draw(img)

    # ================================
    # 每行背景
    # ================================
    if background_style == 1:
        background_y = y

        for i, line in enumerate(lines):
            text_width = line_widths[i]
            text_height = line_heights[i]
            x = (png_width - text_width) / 2

            draw.rectangle(
                [
                    x - background_pad,
                    background_y - background_pad,
                    x + text_width + background_pad,
                    background_y + text_height + background_pad,
                ],
                fill=background_color,
            )

            background_y += text_height + line_spacing

    # ================================
    # 第六步：逐 Glyph 绘制文本
    # ================================
    cursor_y = y

    for i, line in enumerate(lines):
        cursor_x = (png_width - line_widths[i]) / 2
        line_height = line_heights[i]  # 当前行的总高度

        for g in line:

            if g.char is None or g.style is None:
                cursor_x += g.width
                continue
            if emoji.is_emoji(g.char):
                emoji_name = "-".join([f"{ord(c):x}" for c in g.char])
                filepath = os.path.join(emoji_dir, f"emoji_u{emoji_name}.png")
                if os.path.exists(filepath):
                    emj_img = Image.open(filepath).convert("RGBA")
                    # 缩放和对齐（底部对齐）
                    emj_size = g.style.font_size  # 或 g.style.font_size - 5
                    emj_img = emj_img.resize((emj_size, emj_size), Image.LANCZOS)
                    glyph_y = cursor_y + (line_height - emj_size)  # 底部对齐
                    img.alpha_composite(emj_img, (round(cursor_x), round(glyph_y)))
                    cursor_x += g.width
                    continue  # 已经绘制 emoji，跳过普通文字绘制

            font_path = os.path.join(FONT_DIR, f2f[g.style.font_name])
            font = ImageFont.truetype(font_path, g.style.font_size)

            # 计算底部对齐的 y 坐标
            glyph_y = cursor_y + (line_height - (g.style.font_size + 2 * g.style.outline_width))

            # 描边
            if g.style.outline_width > 0:
                for ox in range(-g.style.outline_width, g.style.outline_width + 1):
                    for oy in range(-g.style.outline_width, g.style.outline_width + 1):
                        if ox == 0 and oy == 0:
                            continue
                        draw.text(
                            (cursor_x + ox, glyph_y + oy),
                            g.char,
                            font=font,
                            fill=g.style.outline_color,
                        )

            # 本体
            draw.text(
                (cursor_x, glyph_y),
                g.char,
                font=font,
                fill=g.style.color,
            )

            cursor_x += g.width

        cursor_y += line_heights[i] + line_spacing

    # ================================
    # 第七步：后期变换（scale / rotate）
    # ================================
    content_img = img

    if scale != 1.0:
        new_width = int(img.width * scale / 100)
        new_height = int(img.height * scale / 100)
        content_img = img.resize((new_width, new_height), Image.LANCZOS)

    if rot != 0:
        content_img = content_img.rotate(
            -rot,
            expand=True,
            resample=Image.BICUBIC,
            fillcolor=(0, 0, 0, 0),
        )

    # ================================
    # 第八步：锚点居中贴回画布
    # ================================
    final_img = Image.new("RGBA", (png_width, png_height), (0, 0, 0, 0))

    content_x = anchor_x - content_img.width // 2
    content_y = anchor_y - content_img.height // 2
    print(f"anchor_x: {anchor_x}")
    dst_left = max(content_x, 0)
    dst_top = max(content_y, 0)
    dst_right = min(content_x + content_img.width, png_width)
    dst_bottom = min(content_y + content_img.height, png_height)

    src_left = dst_left - content_x
    src_top = dst_top - content_y
    src_right = src_left + (dst_right - dst_left)
    src_bottom = src_top + (dst_bottom - dst_top)

    if dst_right > dst_left and dst_bottom > dst_top:
        cropped = content_img.crop((src_left, src_top, src_right, src_bottom))
        final_img.paste(cropped, (dst_left, dst_top), cropped)
    else:
        final_img.paste(content_img, (content_x, content_y))

    final_img.save(save_path)
    return save_path


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

    font_path = "baotuxiaobaiti"
    # font_path = f"./fonts/{f2f["baotuxiaobaiti"]}"
    img = create_subtitle_png(
        "你好🌟世界🫶再见🐬🔒，你好🌟世界🫶再见🐬🔒，你好🌟世界🫶再见🐬🔒\n",
        font_path,
        anchor_x=960,
        anchor_y=900,
        font_size=60,
        font_color=(255, 255, 0, 255),
        outline_color=(0, 0, 255, 255),
        outline_width=3,
        background_style=2,  # 改成 1 看每行背景
        background_color=(85, 68, 136, 119),
        background_pad=20,
        save_path="subtitle_final.png",
        scale = 100,
        rot=0,
        word_config= word_config
    )