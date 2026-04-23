"""
绘制字幕 rgba 图片
使用 skia 调用 gpu
todo word_config 暂未实现
"""
# 导入标准库和第三方库模块
import math
import numpy
import moderngl
import skia

import os
import sys
import shutil
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
import platform
# 模块级别定义常量，避免重复构造对象
_BASE_DIR = Path(__file__).resolve().parent
# 字体目录固定指向项目的 src/fonts（与 utils 同级）
_FONT_DIR = _BASE_DIR.parent/"fonts"

def _create_gl_context() -> moderngl.Context | None:
    """创建可用于无头环境的 ModernGL 上下文，失败时返回 None。"""
    """
    这组信息已经把根因锁定了：

    你的 EGL 现在走的是 Mesa，不是 NVIDIA
    证据是 /usr/share/glvnd/egl_vendor.d/ 里只有 50_mesa.json，没有 NVIDIA 的 vendor json
    所以会出现 eglInitialize failed (0x3001) 和 dri2 screen 警告
    osmesa 报错是 glcontext 这个 Python 包当前不含 osmesa backend，不是你命令写错
    下面给你可直接执行的修复清单。

    第一步：补齐 NVIDIA 的 EGL 用户态组件（最关键）

    先查有哪些 580 包可用：
    apt-cache search nvidia | grep -E "580|egl|glvnd|libnvidia-gl|nvidia-utils"

    然后安装（名称以你仓库实际为准，优先 580）：
    sudo apt update
    sudo apt install -y libnvidia-gl-580 nvidia-utils-580

    安装后检查：
    ldconfig -p | grep -E "libEGL_nvidia|libnvidia-eglcore"
    ls -l /usr/share/glvnd/egl_vendor.d/

    期望看到：

    libEGL_nvidia.so.0
    10_nvidia.json 或类似 nvidia 的 json 文件
    如果包装了库但没自动生成 json，可手动补一个：
    sudo tee /usr/share/glvnd/egl_vendor.d/10_nvidia.json >/dev/null <<EOF
    {
    "file_format_version": "1.0.0",
    "ICD": {
    "library_path": "libEGL_nvidia.so.0"
    }
    }
    EOF

    第二步：用无头参数验证 EGL

    unset DISPLAY
    export EGL_PLATFORM=surfaceless
    python3 -c "import moderngl; c=moderngl.create_standalone_context(backend='egl'); print('EGL OK', c.version_code)"

    第三步：如果还想用 osmesa 兜底（可选）

    先装系统库：
    sudo apt install -y libosmesa6 libosmesa6-dev build-essential pkg-config python3-dev

    再让 glcontext 从源码编译（wheel 常不带 osmesa）：
    pip uninstall -y glcontext
    pip install --no-binary glcontext glcontext

    验证：
    python3 -c "import moderngl; c=moderngl.create_standalone_context(backend='osmesa'); print('OSMESA OK', c.version_code)"
    """
    system = platform.system().lower()

    if system == "linux":
        # Linux 服务器优先 EGL（NVIDIA/无头常见方案），再尝试 OSMesa，最后回退 X11。
        candidates = ["egl", "osmesa", "x11"]
    elif system == "windows":
        candidates = [None, "wgl"]
    else:
        candidates = [None]

    last_error = None
    for backend in candidates:
        try:
            if backend is None:
                return moderngl.create_standalone_context()
            return moderngl.create_standalone_context(backend=backend)
        except Exception as exc:
            last_error = exc

    display = os.environ.get("DISPLAY")
    print(
        f"[skia_text_render] GL context 初始化失败，降级为 CPU 渲染 "
        f"(platform={system}, DISPLAY={display!r}, error={last_error!r})"
    )
    return None

# --- ICU data bootstrap (Windows/Conda 常见问题) ---
# skia-python 的 ICU loader 默认会在 python.exe 同目录找 icudtl.dat；
# conda 环境下该文件通常位于 site-packages 里，需显式设置 ICU_DATA 指向它所在目录。
_ICU_DTL = None
try:
    _site_packages_dir = Path(skia.__file__).resolve().parent
    _candidate = _site_packages_dir / "icudtl.dat"
    if _candidate.exists():
        _ICU_DTL = _candidate
        os.environ.setdefault("ICU_DATA", str(_candidate.parent))
except Exception:
    # 不阻断导入；后续若 ICU 初始化失败会报更明确异常
    _ICU_DTL = None

# 创建 ModernGL 上下文，保持当前 OpenGL 环境
_ctx = _create_gl_context()
# 创建 Skia GPU 上下文，避免每次渲染都重新初始化
_GR_CONTEXT = skia.GrDirectContext.MakeGL() if _ctx is not None else None
_USE_GPU = _ctx is not None and _GR_CONTEXT is not None
# 预先创建 Unicode 对象和本地字体管理器，避免每次调用重新加载
_UNICODES = skia.Unicodes.ICU.Make()
if _UNICODES is None:
    # 这里如果返回 None，后续 ParagraphBuilder 会渲染为空或异常；直接给出可操作的错误信息
    raise RuntimeError(
        "Skia ICU 初始化失败：找不到/加载失败 icudtl.dat。"
        f"已尝试设置 ICU_DATA={os.environ.get('ICU_DATA')!r}，"
        f"探测到 icudtl.dat={str(_ICU_DTL) if _ICU_DTL else None}。"
        "请确认该文件存在且进程有权限读取。"
    )
# 本地字体管理器：项目 src/fonts
_LOCAL_FONT_MGR = skia.FontMgr.New_Custom_Directory(str(_FONT_DIR))
# 系统默认字体管理器：用于兜底回退（Windows 上可覆盖更多字符集/emoji）
_SYS_FONT_MGR = skia.FontMgr.RefDefault()
# 缓存已创建的 GPU Surface，按 (width, height) 复用，避免每次重新分配 GPU 内存
# 使用 LRU 策略限制缓存数量，防止长时间运行时显存无限增长
_MAX_SURFACE_CACHE = 8
_surface_cache: OrderedDict[tuple[int, int], skia.Surface] = OrderedDict()
# 模块级 FontCollection，避免每次渲染重新创建
# 说明：skia-python(144.*) 的 FontCollection 只暴露 setDefaultFontManager；
# 因此这里直接使用项目字体目录对应的 FontMgr 作为默认字体源（字幕字体都在 src/fonts）。
_FONT_COLLECTION = skia.textlayout.FontCollection()
_FONT_COLLECTION.setDefaultFontManager(_LOCAL_FONT_MGR)
# # Paragraph 布局宽度：固定足够大的值，避免字幕文字意外换行，同时使缓存 key 与输出分辨率无关
# _PARAGRAPH_MAX_WIDTH = 16384
# 字体样式映射，避免在热路径中重复创建 FontStyle 对象
_FONT_STYLE_MAP: dict[str, skia.FontStyle] = {
    'normal': skia.FontStyle.Normal(),
    'bold': skia.FontStyle.Bold(),
    'italic': skia.FontStyle.Italic(),
    'bold_italic': skia.FontStyle.BoldItalic(),
}
# 避免 .get(key, skia.FontStyle.Normal()) 每次 fallback 创建新对象
_DEFAULT_FONT_STYLE = _FONT_STYLE_MAP['normal']
# 默认输出分辨率，供函数签名默认值及批量渲染 fallback 使用
_DEFAULT_PNG_WIDTH = 1920
_DEFAULT_PNG_HEIGHT = 1080
# 自动换行宽度相对大图最大宽度的内缩值（px）。
# 当 wrap_width <= 0 时，实际布局宽度 = png_width - _AUTO_WRAP_WIDTH_MARGIN_PX。
_AUTO_WRAP_WIDTH_MARGIN_PX = 50


def _get_surface(width: int, height: int) -> skia.Surface:
    """按尺寸获取（或创建）Surface，相同尺寸直接复用，LRU 淘汰超出上限的条目。"""
    key = (width, height)
    if key in _surface_cache:
        _surface_cache.move_to_end(key)
        return _surface_cache[key]
    info = skia.ImageInfo.MakeN32Premul(width, height)
    if _USE_GPU:
        surface = skia.Surface.MakeRenderTarget(_GR_CONTEXT, skia.Budgeted.kNo, info)
    else:
        surface = skia.Surface.MakeRaster(info)
    if surface is None:
        mode = "GPU" if _USE_GPU else "CPU"
        raise RuntimeError(f"Skia {mode} Surface 创建失败: {width}x{height}")
    _surface_cache[key] = surface
    if len(_surface_cache) > _MAX_SURFACE_CACHE:
        _surface_cache.popitem(last=False)
    return surface


def _argb_to_color(argb) -> int:
    """将颜色值转换为 Skia 内部的 ARGB 整数表示。

    参数:
      argb: 整数时按 0xAARRGGBB 解析（ARGB 顺序）；
            元组/列表时按 (R, G, B) 或 (R, G, B, A) 解析（RGBA 顺序）。
    返回:
      Skia ColorSetARGB 生成的整型颜色值。
    """
    if isinstance(argb, int):
        alpha = (argb >> 24) & 0xFF
        red = (argb >> 16) & 0xFF
        green = (argb >> 8) & 0xFF
        blue = argb & 0xFF
        return skia.ColorSetARGB(alpha, red, green, blue)

    if isinstance(argb, (tuple, list)):
        if len(argb) == 3:
            red, green, blue = argb
            alpha = 255
        elif len(argb) == 4:
            red, green, blue, alpha = argb
        else:
            raise ValueError("颜色元组必须是长度为3或4")
        return skia.ColorSetARGB(alpha, red, green, blue)

    raise TypeError("颜色必须是 ARGB 整数或 RGBA 元组")


def _color_is_visible(color) -> bool:
    """判断颜色是否可见（alpha > 0）。支持 0xAARRGGBB 整数和 (R,G,B) / (R,G,B,A) 元组。"""
    if isinstance(color, int):
        return (color >> 24) & 0xFF > 0
    if isinstance(color, (tuple, list)):
        if len(color) == 3:
            return True  # 无 alpha 分量，默认 255
        if len(color) == 4:
            return color[3] > 0
    return False


@lru_cache(maxsize=256)
def _load_font(font_name: str, font_size: float) -> skia.Font:
    """按字体名加载 Skia Font：优先本地字体目录，不存在时回退到系统字体，最终回退到系统默认字体。"""
    typeface = _LOCAL_FONT_MGR.matchFamilyStyle(font_name, skia.FontStyle.Normal())
    if typeface is None:
        typeface = _SYS_FONT_MGR.matchFamilyStyle(font_name, skia.FontStyle.Normal())
    if typeface is None:
        typeface = _SYS_FONT_MGR.matchFamilyStyle("", skia.FontStyle.Normal())
    return skia.Font(typeface, font_size)


@lru_cache(maxsize=1024)
def _build_paragraph_cached(
        line_text: str,
        family_names: tuple[str, ...],
        font_size: float,
        letter_spacing: float,
        font_style_key: str,
        color_int: int,
        is_stroke: bool,
        stroke_width: float,
        layout_width: int,
) -> skia.textlayout.Paragraph:
    """构建并缓存 Paragraph 对象，相同参数直接复用，避免重复 build 的高开销。"""
    font_style_obj = _FONT_STYLE_MAP.get(font_style_key, _DEFAULT_FONT_STYLE)

    paint = skia.Paint(AntiAlias=True)
    if is_stroke:
        paint.setStyle(skia.Paint.kStroke_Style)
        paint.setStrokeWidth(stroke_width)
        paint.setStrokeJoin(skia.Paint.kRound_Join)
    else:
        paint.setStyle(skia.Paint.kFill_Style)
    paint.setColor(color_int)

    ts = skia.textlayout.TextStyle()
    ts.setFontSize(font_size)
    ts.setFontFamilies(list(family_names))
    ts.setFontStyle(font_style_obj)
    ts.setLetterSpacing(letter_spacing)
    ts.setForegroundPaint(paint)

    para_style = skia.textlayout.ParagraphStyle()
    if is_stroke:
        para_style.setTextStyle(ts)

    builder = skia.textlayout.ParagraphBuilder.make(para_style, _FONT_COLLECTION, _UNICODES)
    builder.pushStyle(ts)
    builder.addText(line_text)
    builder.pop()
    paragraph = builder.Build()
    paragraph.layout(layout_width)
    return paragraph


@lru_cache(maxsize=4096)
def _get_font_for_codepoint_styled(
        codepoint: int,
        family_names: tuple[str, ...],
        font_size: float,
        font_style_key: str,
) -> skia.Font:
    """按码点、字体族、字号和样式获取 Font，结果缓存，供弯曲文字逐字渲染使用。"""
    style = _FONT_STYLE_MAP.get(font_style_key, _DEFAULT_FONT_STYLE)
    for mgr in (_LOCAL_FONT_MGR, _SYS_FONT_MGR):
        for family in family_names:
            typeface = mgr.matchFamilyStyle(family, style)
            if typeface is None:
                continue
            if typeface.unicharToGlyph(codepoint) != 0:
                return skia.Font(typeface, font_size)
    fallback = _SYS_FONT_MGR.matchFamilyStyleCharacter("", style, ["zh", "en"], codepoint)
    if fallback is not None:
        return skia.Font(fallback, font_size)
    # 最终 fallback：使用系统默认字体，避免 skia.Typeface() 空字形
    default_typeface = _SYS_FONT_MGR.matchFamilyStyle("", style)
    return skia.Font(default_typeface, font_size)


def _render_curved_text(
        canvas: skia.Canvas,
        text: str,
        family_names: tuple[str, ...],
        font_size: float,
        font_style_key: str,
        letter_spacing: float,
        font_color_int: int,
        need_stroke: bool,
        stroke_width: float,
        stroke_color_int: int,
        curve_degree: float,
        cx: float,
        cy: float,
) -> None:
    """沿圆弧逐字渲染文字。

    正值=凸弧（圆心在下，文字向上弯）；负值=凹弧（圆心在上，文字向下弯）；
    ±360 时首尾衔接成完整圆。每个字符独立定位并旋转以贴合弧线切线方向。
    (cx, cy) 为弧线中点（整体文字的水平中心字符所在位置）。
    """
    char_data: list[tuple[str, float, skia.Font]] = []
    for char in text:
        font = _get_font_for_codepoint_styled(ord(char), family_names, font_size, font_style_key)
        advance = font.measureText(char)
        char_data.append((char, advance, font))

    if not char_data:
        return

    total_width = sum(w for _, w, _ in char_data) + letter_spacing * max(len(char_data) - 1, 0)
    arc_rad = abs(curve_degree) * math.pi / 180.0
    if arc_rad < 1e-9:
        return

    R = total_width / arc_rad
    sign = 1.0 if curve_degree > 0 else -1.0

    fill_paint = skia.Paint(AntiAlias=True)
    fill_paint.setStyle(skia.Paint.kFill_Style)
    fill_paint.setColor(font_color_int)

    stroke_paint = None
    if need_stroke:
        stroke_paint = skia.Paint(AntiAlias=True)
        stroke_paint.setStyle(skia.Paint.kStroke_Style)
        stroke_paint.setStrokeWidth(stroke_width)
        stroke_paint.setStrokeJoin(skia.Paint.kRound_Join)
        stroke_paint.setColor(stroke_color_int)

    # 正值（凸弧）：圆心在 cy + R；负值（凹弧）：圆心在 cy - R
    # 弧线中点对应角度：正值 = -π/2（圆心正上方），负值 = +π/2（圆心正下方）
    # 角度公式：θ = theta_mid + sign * (s_center - total_width/2) / R
    # 旋转公式：rotation_deg = degrees(sign * d / R)，确保字符切线方向与弧线一致
    s_cum = 0.0
    for char, advance, font in char_data:
        d = (s_cum + advance / 2.0) - total_width / 2.0
        theta = -sign * math.pi / 2.0 + sign * d / R
        x = cx + R * math.cos(theta)
        y = (cy + sign * R) + R * math.sin(theta)
        rotation_deg = math.degrees(sign * d / R)

        canvas.save()
        canvas.translate(x, y)
        canvas.rotate(rotation_deg)
        if stroke_paint is not None:
            canvas.drawString(char, -advance / 2.0, 0, font, stroke_paint)
        canvas.drawString(char, -advance / 2.0, 0, font, fill_paint)
        canvas.restore()

        s_cum += advance + letter_spacing


def _apply_canvas_transform(
        canvas: skia.Canvas,
        anchor_x: float, anchor_y: float,
        rotation: float, scale: float,
) -> bool:
    """应用缩放/旋转变换，返回是否实际做了变换（供 restore 判断）。"""
    need_rotation = rotation % 360 != 0
    need_scale = scale != 1.0
    if need_rotation or need_scale:
        canvas.save()
        canvas.translate(anchor_x, anchor_y)
        if need_rotation:
            canvas.rotate(rotation)
        if need_scale:
            canvas.scale(scale, scale)
        canvas.translate(-anchor_x, -anchor_y)
        return True
    return False


def _render_to_surface(
        text: str,
        curve_degree: float = 0.0,
        wrap_width: float = 0.0,
        text_transform: str = None,
        font_name: str = 'Songti SC',
        font_size: float = 20.0,
        font_color: int | tuple = 0x00000000,
        letter_spacing: float = 0.0,
        text_style: str = 'normal',

        stroke_width: float = 0.0,
        stroke_color: int | tuple = 0x00000000,

        background_style: int = 0,
        background_color: int | tuple = 0x00000000,
        background_fill_width: float = 0.0,
        background_fill_height: float = 0.0,
        background_offset_x: float = 0.0,
        background_offset_y: float = 0.0,
        background_radius: float = 12.0,

        alignment: str = 'center',

        line_spacing: float = 0.0,

        scale: float = 1.0,
        rotation: float = 0.0,
        anchor_x: int = 960,
        anchor_y: int = 540,
        png_width: int = _DEFAULT_PNG_WIDTH,
        png_height: int = _DEFAULT_PNG_HEIGHT,
) -> skia.Surface:
    """使用 Skia GPU 渲染文本，按照指定流程处理。

    流程：
    1. 弯曲模式，忽略换行（换行替换成空格，且当360度时尾部需要加一个空格，避免首尾字符重叠），将全文视为单行沿弧渲染；否则，先拆行，以行为单位，依据文字内容、换行宽度、大小写状态、字体、字号、文字颜色、字间距、文字样式，处理绘字。
    2. 按1的结果，依据描边粗细、描边颜色，处理文字描边。
    3. 按2的结果，依据背景样式、背景颜色、填充高度、填充宽度、上下偏移、左右偏移、圆角，处理单行背景（注意背景在文字下方）。
    4. 按3的结果，依据左右对齐方式，处理每行左右方向上的相对定位，包括左对齐、左右中心对齐、右对齐。
    5. 按4的结果，依据行间距，处理每行上下方向上的相对定位。
    6. 按5的结果，视作一个整体，参考系设定大图左上角为（0，0），以整体的中心、图片的宽高、锚定xy，处理在大图上的绝对定位。
    7. 按6的结果，依据缩放、旋转，处理整体变换。
    8. 按需保存、收尾。

    参数:
      text: 要渲染的文字内容，可包含换行符。
      curve_degree: 文字弯曲度数，0=不弯曲，正值=凸弧（向上弯），负值=凹弧（向下弯），±360=首尾衔接的圆。
        启用时忽略换行，将全文视为单行沿弧渲染；wrap_width、alignment、line_spacing、background_style 在此模式下无效。
      wrap_width: 自动换行宽度，单位为像素；当 wrap_width <= 0 时，
        自动使用 png_width - _AUTO_WRAP_WIDTH_MARGIN_PX 作为换行宽度。
      text_transform: 文字大小写转换，'uppercase'=全大写，'lowercase'=全小写，'capitalize'=每词首字母大写，None=不转换。
      font_name: 主字体名称。
      font_size: 字体大小，单位为像素。
      font_color: 文字颜色，支持 0xAARRGGBB 和 (R,G,B,A)。
      letter_spacing: 字符之间的额外间距，单位为像素。
      text_style: 文字样式，'normal', 'bold', 'italic', 'bold_italic'。

      stroke_width: 字体描边宽度，单位为像素，0 表示不描边。
      stroke_color: 字体描边颜色，支持 0xAARRGGBB 和 (R,G,B,A)。

      background_style: 0=无背景, 1=文字形状背景, 2=包围所有文字的矩形背景。
      background_color: 背景颜色，支持 0xAARRGGBB 和 (R,G,B,A)。
      background_fill_width: 背景额外填充宽度，单位为像素。
      background_fill_height: 背景额外填充高度，单位为像素。
      background_offset_x: 背景左右偏移，单位为像素，正值向右。
      background_offset_y: 背景上下偏移，单位为像素，正值向下。
      background_radius: 背景圆角，取值范围 [0.0, 180.0]，单位为像素，0=直角，180=最大圆角。

      alignment: 对齐方式，'left', 'center', 'right'。

      line_spacing: 行间距额外高度，单位为像素。

      scale: 文本和背景整体缩放比例，1.0 为原始大小。
      rotation: 文本和背景整体旋转角度，单位为度，顺时针为正。
      anchor_x: 缩放与旋转的中心点 X 坐标，单位为像素。
      anchor_y: 缩放与旋转的中心点 Y 坐标，单位为像素。
      png_width: 输出 PNG 宽度，单位为像素。
      png_height: 输出 PNG 高度，单位为像素。
    返回:
      已完成绘制但尚未 flush 的 skia.Surface，供调用方按需 flush 并读取像素。
    """

    # font_size=0 或 font_color 全透明时，文字不可见，直接输出透明大图
    _need_draw_text = (font_size > 0) and _color_is_visible(font_color)
    if not _need_draw_text:
        surface = _get_surface(png_width, png_height)
        surface.getCanvas().clear(0x00000000)
        return surface

    # 步骤1: 弯曲模式，忽略换行，将全文视为单行沿弧渲染；否则，先拆行，以行为单位，依据文字内容、换行宽度、大小写状态、字体、字号、文字颜色、字间距、文字样式，处理绘字。
    if text_transform == 'uppercase':
        text = text.upper()
    elif text_transform == 'lowercase':
        text = text.lower()
    elif text_transform == 'capitalize':
        text = text.title()

    family_names = (font_name, "Segoe UI Emoji", "Noto Color Emoji", "sans-serif")
    _font_color_int = _argb_to_color(font_color)
    _need_draw_stroke = (stroke_width > 0) and _color_is_visible(stroke_color)
    _stroke_color_int = _argb_to_color(stroke_color) if _need_draw_stroke else 0

    # 弯曲模式：将全文视为单行，忽略换行符，逐字沿弧渲染，早返回
    if curve_degree != 0:
        curve_degree = max(-360.0, min(360.0, curve_degree))
        text = text.replace('\n', ' ')
        if abs(curve_degree) == 360.0:
            text = text + ' '

        surface = _get_surface(png_width, png_height)
        canvas = surface.getCanvas()
        canvas.clear(0x00000000)
        _need_transform = _apply_canvas_transform(canvas, anchor_x, anchor_y, rotation, scale)
        _render_curved_text(
            canvas, text, family_names, font_size, text_style, letter_spacing,
            _font_color_int, _need_draw_stroke, stroke_width, _stroke_color_int,
            curve_degree, anchor_x, anchor_y,
        )
        if _need_transform:
            canvas.restore()
        return surface

    lines = text.split('\n')
    _layout_width = int(wrap_width) if wrap_width > 0 else max(1, int(png_width - _AUTO_WRAP_WIDTH_MARGIN_PX))

    # 步骤1 & 2: 为每一行预构建 Paragraph（填充色）及描边 Paragraph
    # 两者在同一循环中一并构建，避免二次遍历；实际绘制在步骤6定位完成后进行

    # 为每一行准备 Paragraph
    paragraphs: list[skia.textlayout.Paragraph | None] = []  # type: ignore
    stroke_paragraphs: list[skia.textlayout.Paragraph | None] = []  # type: ignore
    line_widths: list[float] = []
    line_heights: list[float] = []

    font = _load_font(font_name, font_size)
    font_metrics = font.getMetrics()
    blank_line_height = font_metrics.fDescent - font_metrics.fAscent + font_metrics.fLeading

    for line in lines:
        if line == "":
            paragraphs.append(None)
            stroke_paragraphs.append(None)
            line_widths.append(0.0)
            line_heights.append(blank_line_height)
            continue

        paragraph = _build_paragraph_cached(
            line, family_names, font_size, letter_spacing, text_style,
            _font_color_int, False, 0.0, _layout_width)
        paragraphs.append(paragraph)
        # 换行时取实际排版后最长行宽
        line_widths.append(paragraph.LongestLine)
        line_heights.append(paragraph.Height)

        if _need_draw_stroke:
            stroke_paragraphs.append(_build_paragraph_cached(
                line, family_names, font_size, letter_spacing, text_style,
                _stroke_color_int, True, stroke_width, _layout_width))
        else:
            stroke_paragraphs.append(None)

    # 步骤4: 按3的结果，依据左右对齐方式，处理每行左右方向上的相对定位，包括左对齐、左右中心对齐、右对齐
    max_width = max(line_widths) if line_widths else 0
    line_lefts: list[float] = []
    for width in line_widths:
        if alignment == 'left':
            line_left = 0.0
        elif alignment == 'center':
            line_left = (max_width - width) / 2
        elif alignment == 'right':
            line_left = max_width - width
        else:
            line_left = 0.0
        line_lefts.append(line_left)

    # 步骤5: 按4的结果，依据行间距，处理每行上下方向上的相对定位
    current_y = 0.0
    line_tops: list[float] = []
    for height in line_heights:
        line_tops.append(current_y)
        current_y += height + line_spacing

    total_height = current_y - line_spacing if line_heights else 0

    # 步骤3: 构建背景边界 text_bounds
    # 注意：步骤3的背景矩形坐标依赖各行最终的 left/top 偏移，因此需在步骤4（对齐）和步骤5（行距）
    # 计算完毕后才能确定，故代码顺序调整为 4→5→3，与概念流程不同。
    # 直接使用 paragraph 尺寸（含 ascent/descent），轻微大于紧凑 glyph 边界，但避免了逐字 glyph 计算
    text_bounds: list[skia.Rect] = []
    for paragraph, width, line_left, line_top in zip(paragraphs, line_widths, line_lefts, line_tops):
        if paragraph is None or width == 0:
            continue
        text_bounds.append(skia.Rect.MakeLTRB(
            line_left, line_top, line_left + width, line_top + paragraph.Height))

    # 步骤6: 按5的结果，视作一个整体，参考系设定大图左上角为（0，0），以整体的中心、图片的宽高、锚定xy，处理在大图上的绝对定位
    # 在相对坐标系中，三种对齐方式的最小左边界均为 0，整体宽度始终等于 max_width
    overall_center_x = max_width / 2
    overall_center_y = total_height / 2
    offset_x = anchor_x - overall_center_x
    offset_y = anchor_y - overall_center_y
    line_lefts = [x + offset_x for x in line_lefts]
    line_tops = [y + offset_y for y in line_tops]
    text_bounds = [
        skia.Rect.MakeLTRB(r.left() + offset_x, r.top() + offset_y, r.right() + offset_x, r.bottom() + offset_y) for r
        in text_bounds]

    # 获取复用的 GPU Surface（相同尺寸不重新分配 GPU 内存）
    surface = _get_surface(png_width, png_height)
    canvas = surface.getCanvas()
    canvas.clear(0x00000000)

    # 步骤7: 按6的结果，依据缩放、旋转，处理整体变换
    # scale=1 且 rotation 为 360 整数倍时变换为恒等变换，跳过以减少不必要的矩阵运算
    _need_transform = _apply_canvas_transform(canvas, anchor_x, anchor_y, rotation, scale)

    # 绘制背景
    _need_draw_background = (background_style in (1, 2)) and _color_is_visible(background_color)
    if _need_draw_background:
        bg_paint = skia.Paint(AntiAlias=True)
        bg_paint.setStyle(skia.Paint.kFill_Style)
        bg_paint.setColor(_argb_to_color(background_color))

        _bg_radius = min(background_radius, 180)
        if background_style == 1:
            path = skia.Path()
            for rect in text_bounds:
                filled_rect = skia.Rect.MakeLTRB(
                    rect.left() - background_fill_width / 2 + background_offset_x,
                    rect.top() - background_fill_height / 2 + background_offset_y,
                    rect.right() + background_fill_width / 2 + background_offset_x,
                    rect.bottom() + background_fill_height / 2 + background_offset_y,
                )
                if _bg_radius > 0:
                    path.addRRect(skia.RRect.MakeRectXY(filled_rect, _bg_radius, _bg_radius))
                else:
                    path.addRect(filled_rect)
            if not path.isEmpty():
                canvas.drawPath(path, bg_paint)
        else:  # background_style == 2
            if text_bounds:
                left = min(r.left() for r in text_bounds)
                top = min(r.top() for r in text_bounds)
                right = max(r.right() for r in text_bounds)
                bottom = max(r.bottom() for r in text_bounds)
                overall_rect = skia.Rect.MakeLTRB(left, top, right, bottom)
                filled_overall = skia.Rect.MakeLTRB(
                    overall_rect.left() - background_fill_width / 2 + background_offset_x,
                    overall_rect.top() - background_fill_height / 2 + background_offset_y,
                    overall_rect.right() + background_fill_width / 2 + background_offset_x,
                    overall_rect.bottom() + background_fill_height / 2 + background_offset_y,
                )
                if _bg_radius > 0:
                    canvas.drawRRect(skia.RRect.MakeRectXY(filled_overall, _bg_radius, _bg_radius), bg_paint)
                else:
                    canvas.drawRect(filled_overall, bg_paint)

    # 步骤1 & 2: 绘制文本（填充）和描边
    for line, paragraph, stroke_paragraph, line_left, line_top in zip(
            lines, paragraphs, stroke_paragraphs, line_lefts, line_tops):
        if not line:
            continue

        if stroke_paragraph is not None:
            stroke_paragraph.paint(canvas, line_left, line_top)
        paragraph.paint(canvas, line_left, line_top)

    if _need_transform:
        canvas.restore()

    return surface


def _flush_and_return(
        surface: skia.Surface,
        png_width: int,
        png_height: int,
        save_path: Path = None,
) -> numpy.ndarray | Path:
    """flush GPU、snapshot，有 save_path 则保存并返回 Path，否则返回 BGRA numpy 数组。"""
    if _GR_CONTEXT is not None:
        _GR_CONTEXT.flushAndSubmit()
    image = surface.makeImageSnapshot()
    if save_path:
        # 防御：若目标路径被误创建成目录（历史残留/并发异常），ffmpeg 会报 "Is a directory"
        if save_path.exists() and save_path.is_dir():
            try:
                shutil.rmtree(save_path)
                print(f"[skia_text_render] WARN removed directory at save_path={save_path}", file=sys.stderr)
            except Exception as e:
                raise RuntimeError(f"save_path exists but is a directory and cannot be removed: {save_path}") from e
        save_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(save_path), skia.kPNG)
        return save_path
    array = numpy.frombuffer(image.tobytes(), dtype=numpy.uint8)
    return array.reshape((png_height, png_width, 4))


def render_text_to_png(
        text: str,
        curve_degree: float = 0.0,
        wrap_width: float = 0.0,
        text_transform: str = None,
        font_name: str = 'Songti SC',
        font_size: float = 20.0,
        font_color: int | tuple = 0x00000000,
        letter_spacing: float = 0.0,
        text_style: str = 'normal',

        stroke_width: float = 0.0,
        stroke_color: int | tuple = 0x00000000,

        background_style: int = 0,
        background_color: int | tuple = 0x00000000,
        background_fill_width: float = 0.0,
        background_fill_height: float = 0.0,
        background_offset_x: float = 0.0,
        background_offset_y: float = 0.0,
        background_radius: float = 12.0,

        alignment: str = 'center',

        line_spacing: float = 0.0,

        scale: float = 1.0,
        rotation: float = 0.0,
        anchor_x: int = 960,
        anchor_y: int = 540,
        png_width: int = _DEFAULT_PNG_WIDTH,
        png_height: int = _DEFAULT_PNG_HEIGHT,

        save_path: Path = None,
) -> numpy.ndarray | Path:
    """单次渲染，flush 后返回 numpy 数组或保存为 PNG 文件。签名与参数含义同 _render_to_surface，新增：

    参数:
      save_path: 保存 PNG 的路径，None 表示不保存。
    返回:
      有 save_path 时保存文件并返回 Path；否则返回 shape=(png_height, png_width, 4) 的 uint8 BGRA numpy 数组。
    """

    surface = _render_to_surface(
        text=text, curve_degree=curve_degree, wrap_width=wrap_width,
        text_transform=text_transform, font_name=font_name, font_size=font_size,
        font_color=font_color, letter_spacing=letter_spacing, text_style=text_style,
        stroke_width=stroke_width, stroke_color=stroke_color,
        background_style=background_style, background_color=background_color,
        background_fill_width=background_fill_width, background_fill_height=background_fill_height,
        background_offset_x=background_offset_x, background_offset_y=background_offset_y,
        background_radius=background_radius, alignment=alignment, line_spacing=line_spacing,
        scale=scale, rotation=rotation, anchor_x=anchor_x, anchor_y=anchor_y,
        png_width=png_width, png_height=png_height,
    )
    return _flush_and_return(surface, png_width, png_height, save_path)


def render_texts_batch(
        items: list[dict],
        chunk_size: int = 100,
) -> list:
    """批量渲染字幕 PNG，减少 CPU-GPU 同步次数。

    相比逐条调用 render_text_to_png，将 N 次 flushAndSubmit 压缩为 ceil(N/chunk_size) 次：
    每个 chunk 内依次绘制，makeImageSnapshot 借助 Skia COW 语义将各帧 backing texture 隔离，
    统一 flushAndSubmit 一次后再集中 readback/保存，从而让 GPU 流水线更充分。

    注意：chunk_size 越大，VRAM 占用越高（每帧约 png_width×png_height×4 字节）。
    1920×1080 BGRA ≈ 8 MB，chunk_size=100 约 800 MB，按实际显存调整。

    参数:
      items: 每项为传给 render_text_to_png 的 kwargs 字典，可含 save_path。
      chunk_size: 每批最多同时持有的 GPU snapshot 数量，默认 100。
    返回:
      与 items 等长的列表，每项对应 render_text_to_png 的返回值
      （有 save_path → Path；否则 → numpy.ndarray）。
    """
    results: list = [None] * len(items)

    for chunk_start in range(0, len(items), chunk_size):
        chunk = items[chunk_start:chunk_start + chunk_size]
        snapshots = []

        for item in chunk:
            kw = dict(item)
            save_path = kw.pop('save_path', None)
            if save_path is not None:
                save_path = Path(save_path)
            w = kw.get('png_width', _DEFAULT_PNG_WIDTH)
            h = kw.get('png_height', _DEFAULT_PNG_HEIGHT)

            surface = _render_to_surface(**kw)
            # makeImageSnapshot 持有当前 backing texture 引用（Skia COW 语义），
            # makeImageSnapshot 借助 Skia COW 语义将当前 backing texture 隔离，
            # 后续 _get_surface 复用同一 surface 对象时会分配新 texture，不影响已持有的快照
            snapshots.append((surface.makeImageSnapshot(), w, h, save_path))

        # 整个 chunk 只做一次 CPU-GPU 同步
        if _GR_CONTEXT is not None:
            _GR_CONTEXT.flushAndSubmit()

        for i, (image, w, h, sp) in enumerate(snapshots):
            if sp:
                if sp.exists() and sp.is_dir():
                    try:
                        shutil.rmtree(sp)
                        print(f"[skia_text_render] WARN removed directory at save_path={sp}", file=sys.stderr)
                    except Exception as e:
                        raise RuntimeError(f"save_path exists but is a directory and cannot be removed: {sp}") from e
                sp.parent.mkdir(parents=True, exist_ok=True)
                image.save(str(sp), skia.kPNG)
                results[chunk_start + i] = sp
            else:
                arr = numpy.frombuffer(image.tobytes(), dtype=numpy.uint8)
                results[chunk_start + i] = arr.reshape((h, w, 4))
        del snapshots  # readback 完成后尽早释放 GPU Image 引用，归还显存

    return results


if __name__ == "__main__":
    import time

    """
    测试单次绘图"""
    print("测试开始")
    t0 = time.perf_counter()
    # 循环单次
    for i in range(1):
        render_text_to_png(
            text="中❤国\n🚀 😊 🫶 🏁 Hello!\n中国 ❤ 🚀 😊 🫶 🏁 Hello!",
            curve_degree=0,
            wrap_width=0,
            text_transform='uppercase',
            font_name="Songti SC",
            font_size=20,
            font_color=(255, 255, 0, 255),
            letter_spacing=0,
            text_style='bold_italic',

            stroke_width=10,
            stroke_color=(255, 0, 0, 255),

            background_style=2,
            background_color=(100, 0, 0, 100),
            background_fill_width=10.0,
            background_fill_height=10.0,
            # background_offset_x=-100.0,
            # background_offset_y=100.0,
            # background_radius=180,

            alignment='right',

            line_spacing=5,

            scale=2.5,
            rotation=0.0,
            anchor_x=1460,
            anchor_y=640,
            png_width=_DEFAULT_PNG_WIDTH,
            png_height=_DEFAULT_PNG_HEIGHT,
            save_path=Path(__file__).resolve().parent / "my_test_gpu_output.png",
        )
    print("绘图完成")
    # # 测试弯曲文字（凸弧 180°）
    # render_text_to_png(
    #     text="中❤国 🚀 Hello World! 你好世界",
    #     curve_degree=180,
    #     font_name="Heiti TC",
    #     font_size=36,
    #     font_color=(255, 255, 0, 255),
    #     letter_spacing=2,
    #     text_style='bold',
    #     stroke_width=6,
    #     stroke_color=(255, 0, 0, 255),
    #     scale=1.0,
    #     anchor_x=960,
    #     anchor_y=400,
    #     png_width=_DEFAULT_PNG_WIDTH,
    #     png_height=_DEFAULT_PNG_HEIGHT,
    #     save_path=Path(__file__).resolve().parent / "my_test_curve_convex.png",
    # )
    # # 测试弯曲文字（凹弧 -180°）
    # render_text_to_png(
    #     text="中❤国 🚀 Hello World! 你好世界",
    #     curve_degree=-180,
    #     font_name="Heiti TC",
    #     font_size=36,
    #     font_color=(100, 200, 255, 255),
    #     letter_spacing=2,
    #     text_style='bold',
    #     stroke_width=6,
    #     stroke_color=(0, 0, 180, 255),
    #     scale=1.0,
    #     anchor_x=960,
    #     anchor_y=680,
    #     png_width=_DEFAULT_PNG_WIDTH,
    #     png_height=_DEFAULT_PNG_HEIGHT,
    #     save_path=Path(__file__).resolve().parent / "my_test_curve_concave.png",
    # )
    # # 测试弯曲文字（完整圆 360°）
    # render_text_to_png(
    #     text="456完整圆形文字排列测试 Hello World 🚀🎉123",
    #     curve_degree=360,
    #     font_name="Heiti TC",
    #     font_size=28,
    #     font_color=(255, 255, 255, 255),
    #     stroke_width=4,
    #     stroke_color=(0, 100, 0, 255),
    #     anchor_x=960,
    #     anchor_y=540,
    #     png_width=_DEFAULT_PNG_WIDTH,
    #     png_height=_DEFAULT_PNG_HEIGHT,
    #     save_path=Path(__file__).resolve().parent / "my_test_curve_circle.png",
    # )
    # exit()

    """
    测试批量绘图"""
    # batch_texts = [
    #     {
    #         "text": f"中❤国\n🚀 😊 🫶 🏁 Hello!\n中国 ❤ 🚀 😊 🫶 🏁 Hello!{i}",
    #         "font_size": 48,
    #         "font_color": (255, 255, 0, 255),
    #         # "save_path": Path(f"{i}.png")
    #     }
    #     for i in range(100)
    # ]
    # t0 = time.perf_counter()
    # results = render_texts_batch(batch_texts, chunk_size=100)
    # print(f'{time.perf_counter()-t0 = }s')
    # exit()

    """
    测试 png 烧录到 mp4 上"""
    # import ffmpeg
    # import os
    #
    # t0 = time.perf_counter()
    # # ffmpeg位置
    # FFMPEG_DIR: Path = Path(r'C:/wsn_code/others/project_x/static/ffmpeg')
    # os.environ["PATH"] = str(FFMPEG_DIR) + os.pathsep + os.environ["PATH"]
    # # 视频信息 {'width': 2160, 'height': 3840, 'duration': 8.522, 'rotation': 0, 'pix_fmt': 'yuv420p', 'codec_name': 'h264'}
    # video_path = Path(r'C:\wsn_code\others\project_x\test_skia\tests\挂壁立式双瓶机制_1.mp4')
    # output_path = video_path.with_name(video_path.stem + "_subtitled_use_png.mp4")
    #
    # # 字幕图
    # subtitle1_png = render_text_to_png(
    #     text="use png 1 中❤国\n🚀 😊 🫶 🏁 Hello!\n中国 ❤ 🚀 😊 🫶 🏁 Hello!",
    #     curve_degree=100,
    #     wrap_width=0,
    #     text_transform='uppercase',
    #     font_name="Heiti TC",
    #     font_size=30,
    #     font_color=(255, 255, 0, 255),
    #     letter_spacing=0,
    #     text_style='bold_italic',
    #
    #     stroke_width=10,
    #     stroke_color=(255, 0, 0, 255),
    #
    #     background_style=2,
    #     background_color=(100, 0, 0, 100),
    #     background_fill_width=10.0,
    #     background_fill_height=10.0,
    #     # background_offset_x=-100.0,
    #     # background_offset_y=100.0,
    #     # background_radius=180,
    #
    #     alignment='right',
    #
    #     line_spacing=5,
    #
    #     scale=2.5,
    #     rotation=0.0,
    #     anchor_x=1000,
    #     anchor_y=2000,
    #     png_width=2160,
    #     png_height=3840,
    #     save_path=Path(__file__).resolve().parent / "my_test_gpu_output_subtitle1.png",
    # )
    # subtitle2_png = render_text_to_png(
    #     text="use png 2 中❤国\n🚀 😊 🫶 🏁 Hello!\n中国 ❤ 🚀 😊 🫶 🏁 Hello!",
    #     curve_degree=360,
    #     wrap_width=0,
    #     text_transform='uppercase',
    #     font_name="Heiti TC",
    #     font_size=30,
    #     font_color=(255, 255, 0, 255),
    #     letter_spacing=0,
    #     text_style='bold_italic',
    #
    #     stroke_width=10,
    #     stroke_color=(255, 0, 0, 255),
    #
    #     background_style=2,
    #     background_color=(100, 0, 0, 100),
    #     background_fill_width=10.0,
    #     background_fill_height=10.0,
    #     # background_offset_x=-100.0,
    #     # background_offset_y=100.0,
    #     # background_radius=180,
    #
    #     alignment='left',
    #
    #     line_spacing=5,
    #
    #     scale=2.5,
    #     rotation=0.0,
    #     anchor_x=500,
    #     anchor_y=2000,
    #     png_width=2160,
    #     png_height=3840,
    #     save_path=Path(__file__).resolve().parent / "my_test_gpu_output_subtitle2.png",
    # )
    #
    # # GPU 烧录：CUDA 解码 + overlay_cuda（2~7 秒）+ NVENC 编码
    # # CUDA 解码（加速）→ CPU overlay（支持 alpha 混合）→ NVENC 编码（加速）
    # # overlay_cuda 不支持带 alpha 通道的 yuva420p 叠加在 nv12 上，故 overlay 在 CPU 完成
    # video_input = ffmpeg.input(str(video_path), hwaccel='cuda')
    # subtitle1_stream = ffmpeg.input(str(subtitle1_png)).video
    # subtitle2_stream = ffmpeg.input(str(subtitle2_png)).video
    #
    # # 先叠加 1~3 秒的 circle，再叠加 3~7 秒的 subtitle
    # video_overlaid = ffmpeg.filter(
    #     [video_input.video, subtitle1_stream],
    #     'overlay',
    #     enable='between(t,1,3)',
    # )
    # video_overlaid = ffmpeg.filter(
    #     [video_overlaid, subtitle2_stream],
    #     'overlay',
    #     enable='between(t,3,7)',
    # )
    # (
    #     ffmpeg
    #     .output(video_overlaid, video_input.audio, str(output_path), vcodec='h264_nvenc', acodec='copy')
    #     .overwrite_output()
    #     .run()
    # )
    # print(f"已保存烧录视频: {output_path}")
    # print(f'{time.perf_counter()-t0 = }s')
    # exit()

    """
    测试 array 烧录到 mp4 上"""
    # import ffmpeg
    # import os

    # t0 = time.perf_counter()
    # # ffmpeg位置
    # FFMPEG_DIR: Path = Path(r'C:/wsn_code/others/project_x/static/ffmpeg')
    # os.environ["PATH"] = str(FFMPEG_DIR) + os.pathsep + os.environ["PATH"]
    # # 视频信息 {'width': 2160, 'height': 3840, 'duration': 8.522, 'rotation': 0, 'pix_fmt': 'yuv420p', 'codec_name': 'h264'}
    # video_path = Path(r'C:\wsn_code\others\project_x\test_skia\tests\挂壁立式双瓶机制_1.mp4')
    # output_path = video_path.with_name(video_path.stem + "_subtitled_use_array.mp4")

    # # render_text_to_png 不传 save_path → 返回 shape=(png_height, png_width, 4) 的 BGRA uint8 numpy 数组
    # subtitle1_array = render_text_to_png(
    #     text="use array 1 你好你好你好呀\n🚀 😊 🫶 🏁 Hello!\n123123456789",
    #     curve_degree=100,
    #     wrap_width=0,
    #     text_transform='uppercase',
    #     font_name="Heiti TC",
    #     font_size=30,
    #     font_color=(255, 255, 0, 255),
    #     letter_spacing=0,
    #     text_style='bold_italic',

    #     stroke_width=10,
    #     stroke_color=(255, 0, 0, 255),

    #     background_style=2,
    #     background_color=(100, 0, 0, 100),
    #     background_fill_width=10.0,
    #     background_fill_height=10.0,

    #     alignment='right',
    #     line_spacing=5,

    #     scale=2.5,
    #     rotation=0.0,
    #     anchor_x=1000,
    #     anchor_y=2000,
    #     png_width=2160,
    #     png_height=3840,
    #     # 无 save_path，返回 numpy array
    # )
    # subtitle2_array = render_text_to_png(
    #     text="use array 2 你好你好你好呀\n🚀 😊 🫶 🏁 Hello!\n123123456789",
    #     # curve_degree=100,
    #     wrap_width=0,
    #     text_transform='uppercase',
    #     font_name="Heiti TC",
    #     font_size=30,
    #     font_color=(255, 255, 0, 255),
    #     letter_spacing=0,
    #     text_style='bold_italic',

    #     stroke_width=10,
    #     stroke_color=(255, 0, 0, 255),

    #     background_style=2,
    #     background_color=(100, 0, 0, 100),
    #     background_fill_width=10.0,
    #     background_fill_height=10.0,

    #     alignment='right',
    #     line_spacing=5,

    #     scale=2.5,
    #     rotation=0.0,
    #     anchor_x=1000,
    #     anchor_y=2000,
    #     png_width=2160,
    #     png_height=3840,
    #     # 无 save_path，返回 numpy array
    # )
    # # subtitle_array: shape=(3840, 2160, 4), dtype=uint8, BGRA（与 ffmpeg pix_fmt=bgra 对应）
    # # pipe: 只有一个 stdin，多路 array 需各自写入临时 raw 文件，再作为独立输入传给 ffmpeg
    # import tempfile
    # _raw_input_opts = dict(format='rawvideo', pix_fmt='bgra', s='2160x3840', r=25)
    # with tempfile.NamedTemporaryFile(delete=False, suffix='.raw') as _f1:
    #     _f1.write(subtitle1_array.tobytes())
    #     _tmp1 = _f1.name
    # with tempfile.NamedTemporaryFile(delete=False, suffix='.raw') as _f2:
    #     _f2.write(subtitle2_array.tobytes())
    #     _tmp2 = _f2.name
    # try:
    #     video_input = ffmpeg.input(str(video_path), hwaccel='cuda')
    #     array1_input = ffmpeg.input(_tmp1, **_raw_input_opts)
    #     array2_input = ffmpeg.input(_tmp2, **_raw_input_opts)
    #     video_overlaid = ffmpeg.filter(
    #         [video_input.video, array1_input.video],
    #         'overlay',
    #         enable='between(t,1,3)',
    #     )
    #     video_overlaid = ffmpeg.filter(
    #         [video_overlaid, array2_input.video],
    #         'overlay',
    #         enable='between(t,4,7)',
    #     )
    #     (
    #         ffmpeg
    #         .output(video_overlaid, video_input.audio, str(output_path), vcodec='h264_nvenc', acodec='copy')
    #         .overwrite_output()
    #         .run()
    #     )
    # finally:
    #     os.unlink(_tmp1)
    #     os.unlink(_tmp2)
    # print(f"已保存烧录视频(array): {output_path}")
    # print(f'{time.perf_counter()-t0 = }s')
    # exit()

    # """
    # 测试 按帧字幕动画 示例：字幕上下移动"""
    # import ffmpeg
    # import os
    #
    # t0 = time.perf_counter()
    # # ffmpeg位置
    # FFMPEG_DIR: Path = Path(r'C:/wsn_code/others/project_x/static/ffmpeg')
    # os.environ["PATH"] = str(FFMPEG_DIR) + os.pathsep + os.environ["PATH"]
    # # 视频信息 {'width': 2160, 'height': 3840, 'duration': 8.522, 'rotation': 0, 'pix_fmt': 'yuv420p', 'codec_name': 'h264'}
    # video_path = Path(r'C:\wsn_code\others\project_x\test_skia\tests\挂壁立式双瓶机制_1.mp4')
    # output_path = video_path.with_name(video_path.stem + "_subtitled_animated.mp4")
    #
    # fps = 30
    # duration = 8.522
    # total_frames = int(duration * fps)  # 255
    # W, H = 2160, 3840
    #
    # # 字幕只渲染一次（内容固定，位置通过 numpy 平移实现动画，避免逐帧 GPU 渲染）
    # subtitle_base = render_text_to_png(
    #     text="字幕动画测试\nHello Animation 🚀你好你好你好呀\n🚀 😊 🫶 🏁 Hello!\n123123456789",
    #     curve_degree=180,
    #     font_name="Heiti TC",
    #     font_size=60,
    #     font_color=(255, 255, 0, 255),
    #     text_style='bold',
    #     stroke_width=8,
    #     stroke_color=(0, 0, 0, 255),
    #     background_style=2,
    #     background_color=(0, 0, 0, 150),
    #     background_fill_width=20.0,
    #     background_fill_height=10.0,
    #     alignment='center',
    #     scale=1.0,
    #     anchor_x=W // 2,
    #     anchor_y=H // 2,  # 基准位置：垂直居中
    #     png_width=W,
    #     png_height=H,
    # )
    #
    # # subtitle_base: shape=(H, W, 4), BGRA uint8
    #
    # # 垂直平移：dy>0 向下，dy<0 向上；空白处填透明
    # _buf = numpy.zeros_like(subtitle_base)  # 循环外分配一次
    #
    #
    # def _shift_vertical(arr: numpy.ndarray, dy: int) -> numpy.ndarray:
    #     _buf.fill(0)  # fill(0) 比 [:]=0 快（底层 memset）
    #     if dy > 0:
    #         _buf[dy:] = arr[:H - dy]
    #     elif dy < 0:
    #         _buf[:H + dy] = arr[-dy:]
    #     else:
    #         _buf[:] = arr
    #     return _buf
    #
    #
    # anim_start_sec = 2.0
    # anim_end_sec = 6.0
    # anim_start_frame = int(anim_start_sec * fps)
    # anim_end_frame = int(anim_end_sec * fps)  # 120 帧
    #
    # video_input = ffmpeg.input(str(video_path), hwaccel='cuda')
    # # itsoffset=anim_start_sec：告诉 ffmpeg 此 pipe 流从 t=2 开始，只需写 120 帧而非 255 帧
    # # 动画范围外由 enable= 控制跳过 overlay，pipe 不需要提供对应帧数据
    # array_input = ffmpeg.input(
    #     'pipe:',
    #     format='rawvideo',
    #     pix_fmt='bgra',
    #     s=f'{W}x{H}',
    #     r=fps,
    #     itsoffset=anim_start_sec,
    # )
    # video_overlaid = ffmpeg.filter(
    #     [video_input.video, array_input.video],
    #     'overlay',
    #     enable=f'between(t,{anim_start_sec},{anim_end_sec})',
    # )
    # process = (
    #     ffmpeg
    #     .output(video_overlaid, video_input.audio, str(output_path), vcodec='h264_nvenc', acodec='copy')
    #     .overwrite_output()
    #     .run_async(pipe_stdin=True)
    # )
    #
    # amplitude = 100  # 上下浮动幅度（像素）
    # # 只写动画区间帧（120帧），pipe 吞吐量减半
    # for frame_idx in range(anim_start_frame, anim_end_frame):
    #     t_anim = (frame_idx - anim_start_frame) / fps
    #     dy = int(amplitude * math.sin(2 * math.pi * 0.5 * t_anim))
    #     frame_arr = _shift_vertical(subtitle_base, dy)
    #     process.stdin.write(memoryview(frame_arr))  # memoryview 避免 tobytes() 的数据复制
    #
    # process.stdin.close()
    # process.wait()
    # print(f"已保存字幕动画视频: {output_path}")
    # print(f'{time.perf_counter()-t0 = }s')
    # exit()
