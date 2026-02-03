import os
import math
import subprocess
from dataclasses import dataclass
from typing import List

from utils.general_utils import get_video_info, VideoInfo
from utils.log_utils import logger as log

@dataclass
class SpriteGenerateResult:
    sprite_paths: List[str]
    video_width: int
    video_height: int

def generate_sprite(video_path: str, output_dir: str, fps: int = 6, rows: int = 30) -> SpriteGenerateResult:
    """
    生成视频雪碧图

    Args:
        video_path: 视频路径
        output_dir: 雪碧图保存目录
        fps: 每秒抽帧数量，默认6
        rows: 每张雪碧图行数，默认30

    Returns:
        SpriteGenerateResult:
            - sprite_paths: 雪碧图路径列表
            - video_width: 视频显示宽度
            - video_height: 视频显示高度
    """
    os.makedirs(output_dir, exist_ok=True)

    # 获取视频时长,宽高
    video_info: VideoInfo = get_video_info(video_path, need_rotation=True)
    width, height, duration, rot, _ , _ = video_info.get_info()
    if abs(rot) in [90,270]:
        width, height = height, width

    cols = 12
    rows = 20
    fps = 6

    # 每张雪碧图的帧数 = 12 * 20 = 240
    frames_per_sprite = cols * rows

    total_frames = math.ceil(duration * fps)
    sprite_count = math.ceil(total_frames / frames_per_sprite)

    sprite_paths = []
    if width <= height:
        scale_expr = "120:-1"  # 竖视频 / 方视频 → 短边=宽
    else:
        scale_expr = "-1:120"  # 横视频 → 短边=高
    for i in range(sprite_count):
        start_time = i * frames_per_sprite / fps  # 每张 40 秒
        sprite_name = f"sprite_{i + 1}.webp"
        sprite_path = os.path.join(output_dir, sprite_name)
        sprite_paths.append(sprite_path)



        cmd = [
            "ffmpeg",
            "-ss", str(start_time),
            "-i", video_path,
            "-vf", f"fps={fps},scale={scale_expr},tile={cols}x{rows}",
            "-vframes", "1",
            "-y",
            sprite_path
        ]

        log.info(f"生成雪碧图命令: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)

    log.info(f"生成 {len(sprite_paths)} 张雪碧图: {sprite_paths}")
    return SpriteGenerateResult(
        sprite_paths=sprite_paths,
        video_width=width,
        video_height=height,
    )

if __name__ == '__main__':
    paths = generate_sprite(r"C:\Job\AI\mix\AIGC_video_mix_remake\src\test\test2.mp4", "test")
    print(paths)
