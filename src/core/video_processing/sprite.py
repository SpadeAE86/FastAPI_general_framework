import os
import math
import subprocess
from utils.log_utils import logger as log

def generate_sprite(video_path: str, output_dir: str, fps: int = 6, rows: int = 30) -> list:
    """
    生成视频雪碧图

    Args:
        video_path: 视频路径
        output_dir: 雪碧图保存目录
        fps: 每秒抽帧数量，默认6
        rows: 每张雪碧图行数，默认30

    Returns:
        List[str]: 生成的雪碧图路径列表
    """
    os.makedirs(output_dir, exist_ok=True)

    # 获取视频时长
    cmd_duration = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1", video_path
    ]
    result = subprocess.run(cmd_duration, capture_output=True, text=True)
    duration = float(result.stdout.strip())
    log.info(f"视频时长: {duration}s")
    cols = 12
    rows = 20
    fps = 6

    # 每张雪碧图的帧数 = 12 * 20 = 240
    frames_per_sprite = cols * rows

    total_frames = math.ceil(duration * fps)
    sprite_count = math.ceil(total_frames / frames_per_sprite)

    sprite_paths = []

    for i in range(sprite_count):
        start_time = i * frames_per_sprite / fps  # 每张 40 秒
        sprite_name = f"sprite_{i + 1}.webp"
        sprite_path = os.path.join(output_dir, sprite_name)
        sprite_paths.append(sprite_path)

        cmd = [
            "ffmpeg",
            "-ss", str(start_time),
            "-i", video_path,
            "-vf", f"fps={fps},scale=-1:360,tile={cols}x{rows}",
            "-vframes", "1",
            "-y",
            sprite_path
        ]

        log.info(f"生成雪碧图命令: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)

    log.info(f"生成 {len(sprite_paths)} 张雪碧图: {sprite_paths}")
    return sprite_paths

if __name__ == '__main__':
    paths = generate_sprite(r"C:\Job\AI\mix\AIGC_video_mix_remake\src\test\test2.mp4", "test")
    print(paths)
