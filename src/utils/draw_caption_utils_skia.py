"""
绘制字幕 rgba 图片（Skia GPU）

注意：
- 字体目录固定读取项目 `src/fonts`
- `word_config` 暂未实现（与原提交一致）
"""
from pathlib import Path

from utils.skia_text_render import render_text_to_png

# 字体显示名 → 文件名映射（用于文档/查阅，实际转换只需 _FONT_FAMILY_MAP）
_F2F = {
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

# 将 f2f 键（family + style 格式）转换为 matchFamilyStyle 所需的 family name：
# 规则：去掉末尾的常见字重词（空格分隔或短横线分隔）
_STYLE_WORDS = frozenset([
    "Regular", "Bold", "Medium", "Light", "Semibold",
    "Heavy", "Thin", "Black", "Italic",
])


def _strip_style_suffix(name: str) -> str:
    """去掉 font 名称末尾的字重/样式词，返回 family name。"""
    # 处理 "Family-Style" 格式，如 "SJxingkai-C Regular" 末尾 " Regular"
    # 先处理空格分隔
    parts = name.rsplit(" ", 1)
    if len(parts) == 2 and parts[1] in _STYLE_WORDS:
        return parts[0]
    # 再处理短横线分隔，如 "YRDZST-Semibold"
    parts = name.rsplit("-", 1)
    if len(parts) == 2 and parts[1] in _STYLE_WORDS:
        return parts[0]
    return name


# f2f 显示名 → family name（传给 render_text_to_png 的 font_name）
_FONT_FAMILY_MAP: dict[str, str] = {k: _strip_style_suffix(k) for k in _F2F}


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
        background_style=0,  # 0=无背景，1=每行背景，2=整体背景
        background_color=(0, 0, 0, 128),
        background_pad=10,
        png_width=1920,
        png_height=1080,
        save_path="./fonts/test.png",
        scale=1.0,
        rot=0,
        letter_spacing=4,
        word_config=None,  # 预留，暂不使用
):
    """渲染字幕并保存为 PNG 或返回 numpy 数组。

    参数含义与 render_text_to_png 一致，新增映射：
      texts          → text（透传，支持 \\n 换行）
      outline_color  → stroke_color
      outline_width  → stroke_width
      background_pad → background_fill_width / background_fill_height（同值）
      rot            → rotation
    返回：
      有 save_path 时保存并返回 Path；否则返回 numpy BGRA 数组。
    """
    resolved_font = _FONT_FAMILY_MAP.get(font_name, font_name)
    result = render_text_to_png(

        text=texts,
        font_name=resolved_font,
        anchor_x=anchor_x,
        anchor_y=anchor_y,
        font_size=font_size,
        font_color=font_color,
        stroke_color=outline_color,
        stroke_width=outline_width,
        line_spacing=line_spacing,
        background_style=background_style,
        background_color=background_color,
        background_fill_width=float(background_pad),
        background_fill_height=float(background_pad),
        png_width=png_width,
        png_height=png_height,
        save_path=Path(save_path) if save_path is not None else None,
        scale=scale,
        rotation=rot,
        letter_spacing=letter_spacing,
    )
    # 兼容旧版 PIL：调用方（ffmpeg cmd 拼接）期望字幕 png 路径是 str，而不是 Path
    if isinstance(result, Path):
        return str(result)
    return result


if __name__ == "__main__":
    """
    测试 skia 单线程"""
    from pathlib import Path
    import time
    t0 = time.perf_counter()
    for i in range(100):
        img = create_subtitle_png(
            texts="中国\n🚀 😊 🫶 🏁 Hello!\n中国 ❤ 🚀 😊 🫶 🏁 Hello!",
            font_name="Songti SC Regular",
            # anchor_x=960,
            # anchor_y=640,
            font_size=60,
            font_color=(255, 255, 0, 255),
            outline_color=(0, 0, 255, 255),
            outline_width=3,
            background_style=1,
            background_color=(0, 0, 0, 100),
            # rot=5,
            # scale=1.2,
            letter_spacing=30,
            save_path=f'{Path(__file__).stem}.png',
        )
    print(f'{time.perf_counter()-t0 = }s')
    exit()
