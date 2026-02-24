import asyncio
import json
import os, re, math
import random
import shutil
import subprocess
import time
import urllib.parse
from dataclasses import dataclass
from config.config import vpc
import streamlit as st
from typing import Optional, Tuple
from utils.log_utils import logger as log
from exceptions.ServiceException import ServiceException
from utils.file_utils import generate_temp_filename
from utils.obs_utils import download_from_obs
from utils.redis_client import AsyncRedisClientFactory, RedisClientFactory


class VideoInfo:
    def __init__(self, w, h, d, r, f):
        self.width = w
        self.height = h
        self.duration = d
        self.rotation = r
        self.pix_format = f
    def get_info(self):
        return [self.width, self.height, self.duration, self.rotation, self.pix_format]

# 检查是否为合法的 HEX 颜色（支持 #RGB、#RRGGBB、#RRGGBBAA)
def is_valid_hex_color(color_str):
    pattern = r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$'
    return bool(re.fullmatch(pattern, color_str))

def generate_operator():
    operators = ['+', '-']
    return random.choice(operators)

def decode_chinese_url(url):
    """
    将URL中的中文编码部分解码回中文
    只处理连续3个百分号编码（对应中文字符）
    """

    def decode_match(match):
        try:
            return urllib.parse.unquote(match.group())
        except:
            return match.group()

    # 匹配连续3个百分号编码（对应一个中文字符）
    pattern1 = r'%[A-Fa-f0-9]{2}%[A-Fa-f0-9]{2}%[A-Fa-f0-9]{2}'
    chinese_url = re.sub(pattern1, decode_match, url)
    pattern2 = r'%[A-Fa-f0-9]{2}'
    return re.sub(pattern2, decode_match, chinese_url)

def random_with_system_time():
    system_time = int(time.time() * 1000)
    random_seed = (system_time + random.randint(0, 10000))
    return random_seed

def insert_newlines(text, max_length=12, split_index_list = None):
    """在超过max_length的段落中插入换行符"""
    if not split_index_list:
        split_index_list = []
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

# def insert_newlines_base_on_word_config(text, word_config_list, available_width, font_size = 30):
#     lines = text.split('\n')  # 先按已有换行符分割
#     processed_lines = []
#     cur_word_config_index = 0
#     start = word_config_list[0].start
#     end = word_config_list[0].end
#     idx = 0
#     for line in lines:
#
#         current_width = 0
#         segment = ""
#         for ch in line:
#             tmp_font_size = font_size
#             if idx < start:
#                 pass
#             elif idx < end:
#                 tmp_font_size = word_config_list[cur_word_config_index].font_size
#             else:
#                 cur_word_config_index += 1
#                 start = word_config_list[cur_word_config_index].start
#                 end = word_config_list[cur_word_config_index].end
#             if current_width + tmp_font_size <= 330:
#                 segment += ch
#                 current_width += tmp_font_size
#                 processed_lines.append(segment)
#             else:
#                 current_width = tmp_font_size
#                 processed_lines.append(segment)
#                 segment = ch
#             idx += 1
#         idx += 1 #给被分割吞掉的原本的\n
#     result = "\n".join(processed_lines)
#     return result

def get_images_with_prefix(img_dir, img_file_prefix):
    # 确保提供的是绝对路径
    img_dir = os.path.abspath(img_dir)

    # 持有所有匹配前缀的图片文件的列表
    images_with_prefix = []

    # 遍历img_dir中的文件
    for filename in os.listdir(img_dir):
        # print('filename:', filename)
        # print('img_file_prefix:',img_file_prefix)
        # print(filename.startswith(img_file_prefix))
        # 检查文件名是否以img_file_prefix开头 并且后缀是.jpg
        if filename.startswith(img_file_prefix) and (filename.endswith('.png') or filename.endswith('.jpg')):
            # 构建完整的文件路径
            file_path = os.path.join(img_dir, filename)
            # 确保这是一个文件而不是目录
            if os.path.isfile(file_path):
                images_with_prefix.append(file_path)

    return images_with_prefix


def get_file_from_dir(file_dir, extension):
    extension_list = [ext.strip() for ext in extension.split(',')]
    # 确保提供的是绝对路径
    file_dir = os.path.abspath(file_dir)

    # 所有文件的列表
    file_list = []

    # 遍历file_dir中的文件
    for filename in os.listdir(file_dir):
        # print('filename:', filename)
        file_extension = os.path.splitext(filename)[1]
        # 检查文件名是否以img_file_prefix开头 并且后缀是.txt
        if file_extension in extension_list:
            # 构建完整的文件路径
            file_path = os.path.join(file_dir, filename)
            # 确保这是一个文件而不是目录
            if os.path.isfile(file_path):
                file_list.append(file_path)

    return file_list


def get_file_map_from_dir(file_dir, extension):
    extension_list = [ext.strip() for ext in extension.split(',')]
    # 确保提供的是绝对路径
    # 所有文件的列表
    file_map = {}
    if file_dir is not None and os.path.exists(file_dir):
        file_dir = os.path.abspath(file_dir)

        # 遍历file_dir中的文件
        for filename in os.listdir(file_dir):
            # print('filename:', filename)
            file_extension = os.path.splitext(filename)[1]
            # 检查文件名是否以img_file_prefix开头 并且后缀是.txt
            if file_extension in extension_list:
                # 构建完整的文件路径
                file_path = os.path.join(file_dir, filename)
                # 确保这是一个文件而不是目录
                if os.path.isfile(file_path):
                    file_map[file_path] = os.path.split(file_path)[1]

    return file_map


def get_text_from_dir(text_dir):
    return get_file_from_dir(text_dir, ".txt")


def get_mp4_from_dir(video_dir):
    return get_file_from_dir(video_dir, ".mp4")


def get_session_option(option: str) -> Optional[str]:
    return st.session_state.get(option)


def get_must_session_option(option: str, msg: str) -> Optional[str]:
    result = st.session_state.get(option)
    if not result:
        st.toast(msg, icon="⚠️")
        st.stop()
    return result


def must_have_value(option: str, msg: str) -> Optional[str]:
    if not option:
        st.toast(msg, icon="⚠️")
        st.stop()
    return option


def hex_to_bgra(hex_color):
    hex_color = hex_color.lstrip('#')
    alpha = hex_color[6:8] if len(hex_color) >= 8 else '00'
    rgb = hex_color[:6].ljust(6, '0')
    bgr = rgb[4:6] + rgb[2:4] + rgb[0:2]  # RRGGBB -> BBGGRR
    return f"&H{alpha}{bgr}&"


def hex_to_bgra_v2(hex_color):
    hex_color = hex_color.lstrip('#')
    alpha = hex_color[6:8] if len(hex_color) >= 8 else 'ff'
    rgb = hex_color[:6].ljust(6, '0')
    R, G, B, A = int(rgb[0:2], 16), int(rgb[2:4], 16), int(rgb[4:6], 16), int(alpha, 16)
    return R, G, B, A

@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    duration: float
    rotation: int
    pix_fmt: str
    codec_name: str

    def get_info(self) -> Tuple[int, int, float, int, str, str]:
        """
        用于业务侧一行解包，顺序固定
        """
        return (
            self.width,
            self.height,
            self.duration,
            self.rotation,
            self.pix_fmt,
            self.codec_name,
        )

def get_video_info(video_file, need_rotation = False, original_path="") -> VideoInfo:
    redis_client = RedisClientFactory.get_client()
    if original_path:
        #从redis里查有没有该key的信息
        info = redis_client.get(original_path)
        if info:
            info_dict = json.loads(info)
            return VideoInfo(**info_dict)
    #没找到就重新解析
    command = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,pix_fmt,codec_name',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_file
    ]

    result = subprocess.run(command, capture_output=True)

    output = result.stdout.decode('utf-8').strip().split('\n')
    if not output or output[-1] == '':
        raise ServiceException(423, f"{video_file} file not exist, fail to get video info")
    log.debug(f"output: {output}")
    codec_name = output[0].strip()  # 新增：短编码名称
    width = int(output[1])
    height = int(output[2])
    pix_fmt = output[3].strip()
    duration = float(output[4])
    rot = 0
    if need_rotation:
        get_rot_cmd = ["ffprobe", "-i", video_file]
        rot_result = subprocess.run(get_rot_cmd, capture_output=True, text=True, check=True, encoding='utf-8',
                                    errors='ignore')
        if match := re.search(r"rotation of ([-+]?\d+\.?\d*) degrees", rot_result.stderr):
            rot = int(float(match.group(1)))

    video_info = VideoInfo(
        width=width,
        height=height,
        duration=duration,
        rotation=rot,
        pix_fmt=pix_fmt,
        codec_name=codec_name,
    )
    if original_path:
        redis_client.set(
            original_path,
            json.dumps(video_info.__dict__),
            ex=86400
        )
    return video_info

def run_ffmpeg_command(command, video_name=""):
    try:

        log.info(f"full command: {" ".join(command)}")
        t0 = time.time()

        # ★ 不让 Python 自动 UTF-8 解码
        result = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False  # <-- 关键
        )
        t1 = time.time()

        stdout_bytes, stderr_bytes = result.communicate(timeout=500)
        t2 = time.time()

        # ★ decode 时忽略 FFmpeg 的非法字节
        stdout = stdout_bytes.decode("utf-8", errors="ignore")
        stderr = stderr_bytes.decode("utf-8", errors="ignore")

        log.info(f"FFmpeg启动耗时: {t1 - t0:.2f}s")
        log.info(f"FFmpeg运行耗时: {t2 - t1:.2f}s")

        if result.returncode != 0:
            log.error(stderr)
            raise RuntimeError(f"ffmpeg failed for {video_name}")

        print("Command executed successfully.")

    except Exception as e:
        print(f"An error occurred while execute ffmpeg command {e}")
        raise ServiceException(
            888,
            f"timeout while running command: {command}, Exception {e}"
        )

async def run_ffmpeg_command_async(command, video_name=""):
    try:
        log.debug(f"full command: {command}")
        t0 = time.time()

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        t1 = time.time()

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=500
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise ServiceException(
                888,
                f"timeout while running command: {command}"
            )

        t2 = time.time()

        stdout = stdout_bytes.decode("utf-8", errors="ignore")
        stderr = stderr_bytes.decode("utf-8", errors="ignore")

        log.info(f"FFmpeg启动耗时: {t1 - t0:.2f}s")
        log.info(f"FFmpeg运行耗时: {t2 - t1:.2f}s")

        if process.returncode != 0:
            log.error(stderr)
            raise RuntimeError(f"ffmpeg failed for {video_name}")

        log.info("Command executed successfully.")

        return stdout

    except Exception as e:
        log.exception("ffmpeg execution failed")
        raise ServiceException(
            888,
            f"error while running command: {command}, Exception {e}"
        )

async def delete_folder(folder_name: str):
    shutil.rmtree(folder_name, ignore_errors=True)

async def download_resource(path_list, output_dir=None):
    decode_path_list = [decode_chinese_url(path) for path in path_list]  #把中文unicode转换成中文字符串
    if not output_dir:
        vpc_prefix = vpc + "/"
        path_list = [vpc_prefix+p for p in decode_path_list]
    else:
        download_task = [download_from_obs(p, output_dir) for p in path_list]
        path_list = await asyncio.gather(*download_task)
    return path_list

def extent_audio(audio_file, pad_dur=2):
    temp_file = generate_temp_filename(audio_file)
    # 构造ffmpeg命令
    command = [
        'ffmpeg',
        '-i', audio_file,
        '-af', f'apad=pad_dur={pad_dur}',
        temp_file
    ]
    # 执行命令
    subprocess.run(command, capture_output=True, check=True)
    # 重命名最终的文件
    if os.path.exists(temp_file):
        os.remove(audio_file)
        os.renames(temp_file, audio_file)

if __name__ == "__main__":
    result = get_video_info(r"C:\Users\25065\Downloads\test4.mp4")
    print(result.get_info())
    result = get_video_info(r"C:\Users\25065\Downloads\test4_H.264_1440x2560_AAC_4900.mp4")
    print(result.get_info())
    result = get_video_info(r"C:\Users\25065\Downloads\test4_H.264_360x640_AAC_400.mp4")
    print(result.get_info())