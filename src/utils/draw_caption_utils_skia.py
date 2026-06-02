"""
绘制字幕 rgba 图片（Skia GPU）

注意：
- 字体目录固定读取项目 `src/fonts`
- `word_config` 暂未实现（与原提交一致）
"""
from pathlib import Path

from utils.skia_text_render import render_text_to_png
from utils.skia_text_render import calc_line_spacing

# 前端字体名-传递的参数-实际的字体文件
# 20260515160000 产品要求剔除不安全字体，只保留23个ttf、otf，其中有同名不同粗细的字体，默认只使用Regular，粗细由后续添加粗细参数来调整
FONTS: list = [
  {
    "label": "思源黑体",
    "value": "Source Han Sans CN",
    "file": "SourceHanSansCN-Regular.otf"
  },
  {
    "label": "鸿蒙黑体 (HarmonyOS Sans)",
    "value": "HarmonyOS Sans SC",
    "file": "HarmonyOS_Sans_SC_Regular.ttf"
  },
  {
    "label": "小米兰亭 (MiSans)",
    "value": "MiSans",
    "file": "MiSans-Regular.otf"
  },
  {
    "label": "OPPO 体验体 (OPlusSans)",
    "value": "OPlusSans 3.0",
    "file": "OPlusSans3-Regular.ttf"
  },
  {
    "label": "vivo 雅兰体 (vivo Sans)",
    "value": "vivo Sans",
    "file": "vivoSans-Regular.ttf"
  },
  {
    "label": "荣耀黑体 (HONOR Sans)",
    "value": "HONOR Sans CN",
    "file": "HONORSansCN-Regular.ttf"
  },
  {
    "label": "阿里普惠体",
    "value": "Alibaba PuHuiTi",
    "file": "Alibaba-PuHuiTi-Regular.ttf"
  },
  {
    "label": "阿里健康体",
    "value": "Alibaba Health Font 2.0 CN",
    "file": "AlibabaHealthFont2.0CN-85B.ttf"
  },
  {
    "label": "阿里妈妈刀隶体",
    "value": "Alimama DaoLiTi",
    "file": "阿里妈妈刀隶体-Regular.ttf"
  },
  {
    "label": "阿里妈妈数黑体",
    "value": "Alimama ShuHeiTi",
    "file": "Alimama_ShuHeiTi_Bold.ttf"
  },
  {
    "label": "志莽行书",
    "value": "Zhi Mang Xing",
    "file": "钟齐志莽行书.ttf"
  },
  {
    "label": "彩色表情 (Noto Emoji)",
    "value": "Noto Color Emoji",
    "file": "NotoColorEmoji-Regular.ttf"
  }, # emoji不单独使用
]
ALL_FONT_VALUE: list = [_["value"] for _ in FONTS]


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
    # _font_size = font_size if (png_width > png_height) else (font_size * png_height / png_width)
    _font_size = font_size # fix：20260531 使用上层mixed_video_service中计算好的
    _absolute_x = (anchor_x - (png_width / 2)) / png_width # 还原回后端透传的前端传参，用于测试明确的转换公式
    _anchor_x = int(_absolute_x * (png_width / 2) + (png_width / 2)) # 字幕中心位于最左边时，前端传值-1；字幕中心位于w中轴时，前端传值0；字幕中心位于最右边时，前端传值1 # todo 前端使用16：9画幅且使用竖屏视频时，传参时按画幅的w计算的，会导致产物异常。需要前端传递画幅参数。
    result = render_text_to_png(
        text=texts,
        
        wrap_width = 4096 * 10,
        # fix:前端无主动换行，有多长就多长，居中。同前端表现。
        
        font_name=font_name,
        # fix:产品剔除了不安全字体，只保留了23个，做了映射。
        
        anchor_x=_anchor_x,
        # fix:前端传值（最左=-1，中间=0，最右=1），注意调用方传值计算
        
        anchor_y=anchor_y,
        
        # font_size=font_size,
        font_size=_font_size,
        # fix:前端、后端透传，算法端向前端展示的大小映射。
        # fix:横屏视频文字大小，前端显示和实际产物不一致。横屏时转换回原始fontsize。
        
        font_color=font_color,
        
        font_weight=400,
        # fix:前端默认400，后端不传，算法端向前端展示的大小映射。
        
        stroke_color=outline_color,
        
        #stroke_width=outline_width,
        stroke_width=(outline_width * 3 * png_height / png_width) if (png_width > png_height) else outline_width * 3,
        # fix:前端0-100对应0-5px。当前端使用100时，前端传5，后端传5，对应到skia中需要*3，才能和前端基本一致。
        
        # line_spacing=line_spacing,
        # line_spacing=-1 if (png_width > png_height) else -4,
        line_spacing=int(calc_line_spacing(font_name, font_size=_font_size, line_height_ratio=1.5)),
        # fix:前端展示使用150%字高，前端默认不传，后端以前约定默认传10。对应到skia中需要处理成1.5倍字高，才能和前端基本一致。
        
        # background_style=background_style,
        background_style={0: 0, 1: 2}.get(background_style),
        # fix:前端0时无，后端透传，算法端0；前端1时有，后端透传，算法端2。
        
        background_color=background_color,
        
        # background_fill_width=float(background_pad),
        background_fill_width=0,
        # fix:前端展示为0
        
        # background_fill_height=float(background_pad),
        background_fill_height=int(calc_line_spacing(font_name, font_size=_font_size, line_height_ratio=1.5)),
        # fix:前端展示为行高
        
        background_radius=0,
        # fix:前端展示为直角
        
        png_width=png_width,
        
        png_height=png_height,
        
        save_path=Path(save_path) if save_path is not None else None,
        
        scale=scale,
        
        rotation=rot,
        
        # letter_spacing=letter_spacing,
        letter_spacing=0, 
        # fix:前端默认不传，后端以前约定默认传2。对应到skia中需要处理成0，才能和前端基本一致。
    )
    # 兼容旧版 PIL：调用方（ffmpeg cmd 拼接）期望字幕 png 路径是 str，而不是 Path
    if isinstance(result, Path):
        return str(result)
    return result


if __name__ == "__main__":
    # """
    # 测试 skia 单线程"""
    # from pathlib import Path
    # import time
    # t0 = time.perf_counter()
    # for i in range(100):
    #     img = create_subtitle_png(
    #         texts="中国\n🚀 😊 🫶 🏁 Hello!\n中国 ❤ 🚀 😊 🫶 🏁 Hello!",
    #         font_name="Songti SC Regular",
    #         # anchor_x=960,
    #         # anchor_y=640,
    #         font_size=60,
    #         font_color=(255, 255, 0, 255),
    #         outline_color=(0, 0, 255, 255),
    #         outline_width=3,
    #         background_style=1,
    #         background_color=(0, 0, 0, 100),
    #         # rot=5,
    #         # scale=1.2,
    #         letter_spacing=30,
    #         save_path=f'{Path(__file__).stem}.png',
    #     )
    # print(f'{time.perf_counter()-t0 = }s')
    # exit()
    _strip_style_suffix("Songti SC Regular")
