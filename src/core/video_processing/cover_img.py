@dataclass
class VideoCoverResult:
    cover_path: str
    video_width: int
    video_height: int


def generate_cover(
        video_path: str,
        output_dir: str,
        time_sec: Optional[float] = 0.0,  # 封面时间点，默认视频开头
        width: int = 320,  # 缩略图宽度，保持比例自动计算高度
) -> VideoCoverResult:
    """
    生成视频封面图

    Args:
        video_path: 视频路径
        output_dir: 封面保存目录
        time_sec: 截取时间点（秒），默认0
        width: 缩略图宽度，自动保持比例

    Returns:
        VideoCoverResult:
            - cover_path: 封面图路径
            - video_width: 视频原始宽度
            - video_height: 视频原始高度
    """
    os.makedirs(output_dir, exist_ok=True)

    # 获取视频信息
    from ffprobe3 import FFProbe  # 可用 ffprobe3 或者自定义 get_video_info
    probe = FFProbe(video_path)
    video_stream = next((s for s in probe.streams if s.is_video()), None)
    if not video_stream:
        raise ValueError("无法获取视频流信息")

    width_orig = int(video_stream.video_width)
    height_orig = int(video_stream.video_height)

    # 封面保存路径
    cover_name = "cover.webp"
    cover_path = os.path.join(output_dir, cover_name)

    # 构建 ffmpeg 命令
    cmd = [
        "ffmpeg",
        "-ss", str(time_sec),  # 快速跳转到时间点
        "-i", video_path,
        "-vf", f"scale={width}:-1",  # 宽度固定，高度自动
        "-vframes", "1",  # 只生成一帧
        "-y",
        cover_path
    ]

    print(f"生成封面图命令: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    return VideoCoverResult(
        cover_path=cover_path,
        video_width=width_orig,
        video_height=height_orig
    )