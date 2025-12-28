from utils.log_utils import logger as log
from general_utils import is_valid_hex_color
from draw_caption_utils import create_subtitle_png
import os, re, math

FINAL_DIR = "./final"
FONT_DIR = "./font"
OUTPUT_DIR = "./work"

def hex_to_bgra_v2(hex_color):
    hex_color = hex_color.lstrip('#')
    alpha = hex_color[6:8] if len(hex_color) >= 8 else 'ff'
    rgb = hex_color[:6].ljust(6, '0')
    R, G, B, A = int(rgb[0:2], 16), int(rgb[2:4], 16), int(rgb[4:6], 16), int(alpha, 16)
    return R, G, B, A

def insert_newlines(text, max_length=12):
    """在超过max_length的段落中插入换行符"""
    lines = text.split('\n')  # 先按已有换行符分割
    processed_lines = []
    for line in lines:
        if len(line) <= max_length:
            processed_lines.append(line)
            continue
        # 按max_length分割行
        new_line = []
        current_segment = ""
        for char in line:
            current_segment += char
            if len(current_segment) >= max_length:
                new_line.append(current_segment)
                current_segment = ""
        if current_segment:  # 添加剩余字符
            new_line.append(current_segment)
        processed_lines.append('\n'.join(new_line))
    return '\n'.join(processed_lines)

# font_size: int = Field(default=30, gt=0)
# font_type: Literal[*font_options] = "Songti SC Regular"
# cap_position: Literal[*list(subtitle_position_options.keys())] = "bottom center"
# cap_color: str = "#ffffff"
# cap_outline_color: str = "#000000"
# cap_outline_width: float = Field(ge=0, default=0)
# cap_background_color: str = "#000000ff"
# cap_absolute_x: float = Field(ge=0, default=0)
# cap_absolute_y: float = Field(ge=0, default=0)
# cap_background_type: int = 2
# cap_line_spacing: int = Field(ge=5, default=10)
# cap_letter_indent: int = Field(ge=0, default=2)

class CaptionManager:
    def __init__(self, width, height, cap_config, transition_config, project_id = "test"):
        self.project_id = project_id
        self.cap_config = cap_config.caption_list
        self.font_size = cap_config.font_size
        self.font_type = cap_config.font_type
        self.transition_config = transition_config
        self.color = cap_config.cap_color
        self.background_color = cap_config.cap_background_color
        self.background_type = cap_config.cap_background_type
        self.x = cap_config.cap_absolute_x
        self.y = cap_config.cap_absolute_y
        self.outline_color = cap_config.cap_outline_color
        self.outline_width = cap_config.cap_outline_width
        self.line_spacing = cap_config.cap_line_spacing
        self.letter_indent = cap_config.cap_letter_indent
        self.png_width = width
        self.png_height = height

    def gen_subtitle_png(self, portrait=True,
                         processed_so_far=0, target="", transition_in=0, transition_out=0,
                         last_idx=-1, cap_cnt=1):
        cap_cur = 0
        subtitle_png_list = []
        font_color = hex_to_bgra_v2(self.color)
        outline_color = hex_to_bgra_v2(self.outline_color)
        background_color = hex_to_bgra_v2(self.background_color)
        for idx, caption in enumerate(self.cap_config):
            subtitle_config = {}
            if transition_in > 0 and cap_cur == last_idx:
                caption.end = min(caption.end, caption.end + transition_in / 2)  # 上一段字幕结尾延长到转场中点处
            if transition_in > 0 and cap_cur == last_idx + 1:
                caption.start = max(caption.start, caption.start + transition_in / 2)  # 本身第一段字幕开头延后到转场中点处
            if transition_out > 0 and cap_cur == last_idx + cap_cnt:
                caption.end = min(caption.end, caption.end - transition_out / 2)  # 本身最后一段字幕结尾缩短到转场中点处
            if transition_out > 0 and cap_cur == last_idx + cap_cnt + 1:
                caption.start = max(caption.start, caption.start - transition_out / 2)  # 下一段字幕开头提前到转场中点处
            cap_cur += 1
            if caption.end < processed_so_far:
                continue

            subtitle_config["start"] = max(caption.start - processed_so_far, 0)
            subtitle_config["end"] = caption.end - processed_so_far

            anchor_x, anchor_y = 0, self.png_width * 0.25
            if caption.background_type:
                self.background_type = caption.background_type
            if caption.font_size:
                self.font_size = caption.font_size
            if caption.font_type:
                self.font_type = caption.font_type

            log.debug(f"debug {idx}font_color|{font_color}")
            fc = font_color
            if caption.color and is_valid_hex_color(caption.color):
                fc = hex_to_bgra_v2(caption.color)

            log.debug(f"debug {idx}outline_color|{outline_color}")

            oc = outline_color
            if caption.outline_color and is_valid_hex_color(caption.outline_color):
                oc = hex_to_bgra_v2(caption.outline_color)

            if caption.outline_width:
                self.outline_width = caption.outline_width

            log.debug(f"debug {idx}background_color|{background_color}")

            bc = background_color
            if caption.background_color and is_valid_hex_color(caption.background_color):
                bc = hex_to_bgra_v2(caption.background_color)

            letter_spacing = caption.letter_spacing if caption.letter_spacing else self.letter_indent
            line_spacing = caption.line_spacing if caption.line_spacing else self.line_spacing

            png_subtitle_dir = "/".join(['./work', self.project_id])
            save_path = "/".join([png_subtitle_dir, f"{target}_subtitle{idx}.png"])
            if caption.absolute_x:
                anchor_x = caption.absolute_x
            anchor_y = (1 - 0.25) * self.png_width
            if caption.absolute_y:
                anchor_y = (1 - caption.absolute_y) * self.png_width

            font_size = int(self.png_height / 720 * self.font_size)
            background_pad = int(20 * self.png_height / 720)

            if self.outline_width:
                self.outline_width = max(1, int(self.outline_width * self.png_height / 720))
            create_subtitle_png(caption.cap, self.font_type,
                                anchor_x=int(self.png_width / 2 + anchor_x),
                                anchor_y=int(anchor_y),
                                font_size=font_size,
                                font_color=fc,
                                outline_color=oc,
                                outline_width=int(self.outline_width),
                                line_spacing=line_spacing,
                                background_style=self.background_type,  # 0 = 无背景，1 = 每行背景，2 = 整体背景
                                background_color=bc,  # 半透明黑色
                                background_pad=background_pad,
                                png_width=self.png_width,
                                png_height=self.png_height,
                                save_path=save_path,
                                scale=caption.scale,
                                rot=caption.rotation,
                                letter_spacing=letter_spacing,
                                word_config=getattr(caption, 'word_config', []),
                                )
            subtitle_config["path"] = save_path
            subtitle_png_list.append(subtitle_config)
        return subtitle_png_list


class CapHelper:
    def __init__(self, project_id, width, height, cap_config):
        os.makedirs(f"{OUTPUT_DIR}/{project_id}", exist_ok=True)
        self.project_id = project_id
        self.cap_config = cap_config
        self.cap_list = []
        self.width, self.height = width, height

    def gen_cap_mapping(self):
        subtitle_tasks = []
        self.cap_list = []
        for idx, caption in enumerate(self.cap_config.caption_list):
            anchor_x, anchor_y = self.width * self.cap_config.cap_absolute_x, self.height * self.cap_config.cap_absolute_y
            font_size = caption.font_size if caption.font_size else self.cap_config.font_size
            font_type = caption.font_type if caption.font_type else self.cap_config.font_type
            fc = self.cap_config.cap_color
            oc = self.cap_config.cap_outline_color
            bc = self.cap_config.cap_background_color
            letter_spacing = caption.letter_spacing if caption.letter_spacing else self.cap_config.cap_letter_indent
            line_spacing = caption.line_spacing if caption.line_spacing else self.cap_config.cap_line_spacing
            background_type = caption.background_type if caption.background_type is not None \
                else self.cap_config.cap_background_type
            outline_width = caption.outline_width if caption.outline_width is not None else self.cap_config.cap_outline_width
            if caption.color and is_valid_hex_color(caption.color):
                fc = hex_to_bgra_v2(caption.color)
            if caption.outline_color and is_valid_hex_color(caption.outline_color):
                oc = hex_to_bgra_v2(caption.outline_color)
            if caption.background_color and is_valid_hex_color(caption.background_color):
                bc = hex_to_bgra_v2(caption.background_color)

            png_subtitle_dir = "/".join([OUTPUT_DIR, self.project_id])
            save_path = "/".join([png_subtitle_dir, f"subtitle{idx}.png"])
            if caption.absolute_x:
                anchor_x = caption.absolute_x * self.width
            anchor_y = (1 - self.cap_config.cap_absolute_y) * self.height
            if caption.absolute_y is not None:
                anchor_y = (1 - caption.absolute_y) * self.height

            # Keep track of unscaled font size for text wrapping
            unscaled_font_size = font_size
            font_size = math.ceil(self.height / 720 * font_size)

            background_pad = int(20 * self.height / 720)

            if outline_width:
                outline_width = max(1, int(outline_width * self.height / 720))
            else:
                outline_width = 0

            cap_img = create_subtitle_png(caption.cap, font_type,
                                              anchor_x=int(self.width / 2 + anchor_x),
                                              anchor_y=int(anchor_y),
                                              font_size=font_size,
                                              font_color=fc,
                                              outline_color=oc,
                                              outline_width=int(outline_width),
                                              line_spacing=line_spacing,
                                              background_style=background_type,  # 0 = 无背景，1 = 每行背景，2 = 整体背景
                                              background_color=bc,  # 半透明黑色
                                              background_pad=background_pad,
                                              png_width=self.width,
                                              png_height=self.height,
                                              save_path=save_path,
                                              scale=caption.scale,
                                              rot=caption.rotation,
                                              letter_spacing=letter_spacing,
                                              word_config=caption.word_config,
                                              )
            self.cap_list.append(cap_img)

        log.info(f"generated {self.cap_list}")

    def get_cap_list(self):
        return self.cap_list

    def delete_cap_png(self):
        for idx, cap in enumerate(self.cap_list):
            if os.path.exists(cap):
                os.remove(cap)
