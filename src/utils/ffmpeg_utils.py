import asyncio
import io
import json
import os
import subprocess
import time
import tempfile
import ffmpeg
import wave
import bisect
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from yarl import URL
from json.decoder import JSONDecodeError
from typing import Union, Generator, Iterable, Optional, List
from pymediainfo import MediaInfo

from config.config import FINAL_DIR, MY_CONFIG, ENV, TEMP_DIR
from exceptions.ServiceException import ServiceException
from utils.general_utils import run_ffmpeg_command, get_video_info
from utils.log_utils import logger, time_it, LOG_LEVEL
from models.pydantic_dataclass.transition_caption import TransitionCaption

log = logger

# --- 配置 ---
if 'hw' in MY_CONFIG:
    _DECODER = MY_CONFIG['hw'][ENV]['decoder']
    _ENCODER = MY_CONFIG['hw'][ENV]['encoder']
else:
    _DECODER = 'cpu'
    _ENCODER = 'cpu'

# --- 流分块大小 ---
CHUNK_SIZE: int = 4 * 1024 * 1024  # 4M

# --- ffmpeg 是否不输出控制台日志 ---
_IS_QUIET: bool = True if logger.level(LOG_LEVEL).no > logger.level('TRACE').no else False


@lru_cache(maxsize=1)
def get_hw_capabilities():
    """同步获取硬件信息"""
    try:
        from utils.cmd_utils import run_command
    except ImportError:
        def run_command(cmd, timeout=5):
            res = subprocess.run(cmd, capture_output=True, timeout=timeout)
            return res.returncode, res.stdout, res.stderr
            
    _, hwaccels, _ = run_command(['ffmpeg', '-hwaccels'], timeout=5)
    _, decoders, _ = run_command(['ffmpeg', '-decoders'], timeout=5)
    _, encoders, _ = run_command(['ffmpeg', '-encoders'], timeout=5)
    return hwaccels, decoders, encoders


def get_hw_config(decoder_pref: str = None, encoder_pref: str = None) -> dict:
    if decoder_pref is None:
        decoder_pref = _DECODER
    if encoder_pref is None:
        encoder_pref = _ENCODER

    decoders_map = {
        'qsv': {'hwaccel': 'qsv', 'v_decoder': 'h264_qsv'},
        'cuda': {'hwaccel': 'cuda', 'v_decoder': 'h264_cuvid'},
        'amf': {'hwaccel': 'd3d11va', 'v_decoder': 'h264_amf'},
        'cpu': {'hwaccel': None, 'v_decoder': 'h264'}
    }

    encoders_map = {
        'qsv': {'v_encoder': 'h264_qsv'},
        'cuda': {'v_encoder': 'h264_nvenc'},
        'amf': {'v_encoder': 'h264_amf'},
        'cpu': {'v_encoder': 'libx264'}
    }

    decoder_config = decoders_map.get(decoder_pref.lower(), decoders_map['cpu'])
    encoder_config = encoders_map.get(encoder_pref.lower(), encoders_map['cpu'])

    return {
        'hwaccel': decoder_config['hwaccel'],
        'v_decoder': decoder_config['v_decoder'],
        'v_encoder': encoder_config['v_encoder']
    }


@time_it
def has_audio_stream(video: Union[Path, io.BufferedIOBase, bytes], use_mediainfo: bool = True) -> bool:
    if use_mediainfo:
        if isinstance(video, bytes):
            input_data = io.BytesIO(video)
        else:
            input_data = video

        media_info = MediaInfo.parse(input_data)
        for track in media_info.tracks:
            if track.track_type == 'Audio':
                return True
        return False

    logger.warning('以下 ffprobe 模式 已弃用，请改用 mediainfo 模式。原因：慢')
    return False


@time_it
def extract_audio_from_video(
        video: Path,
        as_path: bool = False,
        audio: Path = None,
        as_gen: bool = False
) -> Union[Path, bytes, Generator[bytes, None, None], None]:
    if as_path:
        as_gen = False

    is_temp_file = False
    input_source = str(video)
    input_args = {
        'vn': None,
        'sn': None,
        'dn': None,
        'fflags': '+fastseek+nobuffer'
    }

    if as_path:
        output_format = 'wav'
        if audio:
            assert audio.suffix == f'.{output_format}'
            output_dest = str(audio)
            Path(output_dest).parent.mkdir(parents=True, exist_ok=True)
        else:
            fd, output_dest = tempfile.mkstemp(suffix=f'.{output_format}', dir=TEMP_DIR)
            os.close(fd)
            is_temp_file = True
    else:
        output_format = 's16le'
        output_dest = 'pipe:'
        
    output_args = {
        'loglevel': 'error' if _IS_QUIET else 'info',
        'format': output_format,
        'acodec': 'pcm_s16le',
        'ar': '44100',
        'ac': 2,
        'threads': 1,
        'map_metadata': -1,
    }

    try:
        process = (
            ffmpeg
            .input(input_source, **input_args)
            .output(output_dest, **output_args)
            .run_async(
                pipe_stdout=not as_path,
                quiet=_IS_QUIET,
                overwrite_output=True,
            )
        )

        if as_gen:
            def _generator():
                try:
                    while True:
                        chunk = process.stdout.read(CHUNK_SIZE)
                        if not chunk:
                            if process.poll() is not None and process.returncode != 0:
                                logger.error(f'提取进程异常退出，Code: {process.returncode}')
                            break
                        yield chunk
                    process.wait()
                finally:
                    if process.stdout: process.stdout.close()
                    if process.stderr: process.stderr.close()
                    if process.poll() is None: process.kill()

            logger.success(f'音频提取成功 -> generator')
            return _generator()

        if as_path:
            process.wait()
            logger.success(f'音频提取成功 -> {output_dest}')
            return Path(output_dest)

        out, _ = process.communicate()
        logger.success(f'音频提取成功 -> bytes')
        return out

    except ffmpeg.Error as e:
        logger.error(f'FFmpeg 提取失败: {e}')
        if is_temp_file and output_dest and os.path.exists(output_dest):
            os.remove(output_dest)
        return None
    except Exception as e:
        logger.exception(f'提取音频发生非预期异常: {e}')
        if is_temp_file and output_dest and os.path.exists(output_dest):
            os.remove(output_dest)
        return None

@time_it
def save_data_to_audio(data: Union[bytes, Iterable[bytes]], audio: Path):
    if not data:
        logger.warning('音频数据为空，跳过保存')
        return False

    process = None
    try:
        process = (
            ffmpeg
            .input('pipe:', **{'format': 's16le', 'ar': '44100', 'ac': 2})
            .output(str(audio), **{
                'loglevel': 'error' if _IS_QUIET else 'info',
                'acodec': 'copy',
                'threads': 1,
            })
            .overwrite_output()
            .run_async(
                pipe_stdin=True,
                quiet=_IS_QUIET,
                overwrite_output=True,
            )
        )

        if isinstance(data, (bytes, bytearray)):
            data_iter = (data[i: i + CHUNK_SIZE] for i in range(0, len(data), CHUNK_SIZE))
        else:
            data_iter = data

        for chunk in data_iter:
            if chunk:
                process.stdin.write(chunk)

        process.stdin.close()
        process.wait()

        if process.returncode == 0:
            logger.success(f'音频已成功流式保存至: {audio}')
            return True
        else:
            logger.error(f'FFmpeg 封装失败，退出码: {process.returncode}')
            return False

    except Exception as e:
        logger.exception(f'音频保存文件时发生非预期异常: {e}')
        return False
    finally:
        if process and process.poll() is None:
            process.kill()


@time_it
def extract_video_info(video: Union[Path, io.BufferedIOBase, bytes], use_mediainfo: bool = True) -> Union[dict, None]:
    if use_mediainfo:
        if isinstance(video, bytes):
            input_data = io.BytesIO(video)
        else:
            input_data = video

        try:
            media_info = MediaInfo.parse(input_data)
        except Exception as e:
            logger.error(f'MediaInfo 解析失败: {e}')
            return None

        video_track = next((t for t in media_info.tracks if t.track_type == 'Video'), None)
        if not video_track:
            logger.error(f'找不到视频流')
            return None

        general_track = next((t for t in media_info.tracks if t.track_type == 'General'), None)

        def _normalize_rotation(rotation_value) -> float:
            if rotation_value == 0:
                ffmpeg_style_rotation = 0
            else:
                ffmpeg_style_rotation = -rotation_value
                if ffmpeg_style_rotation <= -360:
                    ffmpeg_style_rotation %= 360
            return ffmpeg_style_rotation

        def _map_to_ffmpeg_pix_fmt(track) -> str:
            chroma = getattr(track, 'chroma_subsampling', '4:2:0').replace(':', '')
            depth = int(getattr(track, 'bit_depth', 8))
            if depth == 8: return f'yuv{chroma}p'
            elif depth == 10: return f'yuv{chroma}p10le'
            elif depth == 12: return f'yuv{chroma}p12le'
            return f'yuv{chroma}p'

        def _map_to_ffmpeg_codec(track_format) -> str:
            codec_map = {
                'AVC': 'h264', 'HEVC': 'hevc', 'MPEG-4 Visual': 'mpeg4',
                'MPEG Video': 'mpeg2video', 'ProRes': 'prores'
            }
            return codec_map.get(track_format, str(track_format).lower())

        return {
            'width': int(video_track.width or 0),
            'height': int(video_track.height or 0),
            'duration': float(general_track.duration or 0) / 1000.0,
            'rotation': _normalize_rotation(float(getattr(video_track, 'rotation', 0))),
            'pix_fmt': _map_to_ffmpeg_pix_fmt(video_track),
            'codec_name': _map_to_ffmpeg_codec(video_track.format),
        }

    logger.warning('以下 ffprobe 模式 已弃用，请改用 mediainfo 模式。原因：慢')
    full_info = ffmpeg.probe(str(video))

    def _extract_from_probe(full_info: dict) -> Union[dict, None]:
        video_stream = next((s for s in full_info.get('streams', []) if s.get('codec_type') == 'video'), {})
        if not video_stream: return None
        format_info = full_info.get('format', {})
        width = int(video_stream.get('width', 0))
        height = int(video_stream.get('height', 0))
        duration = float(format_info.get('duration', 0))
        rotation = float(([_['rotation'] for _ in video_stream.get('side_data_list', []) if 'rotation' in _] or [0])[0])
        pix_fmt = video_stream.get('pix_fmt', '')
        codec_name = video_stream.get('codec_name', '')
        return {
            "width": width, "height": height, "duration": duration,
            "rotation": rotation, "pix_fmt": pix_fmt, "codec_name": codec_name,
        }
    return _extract_from_probe(full_info)


@time_it
def check_audio_stream_simple(file_path):
    """简化版检查音频流"""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'a',
            '-show_entries', 'stream=codec_type',
            '-of', 'csv=p=0',
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
        return bool(result.stdout.strip())
    except subprocess.TimeoutExpired:
        log.error(f"Timeout checking audio stream for {file_path}")
        return False
    except subprocess.CalledProcessError:
        return False

@time_it
def extract_i_frame_timestamps(video: Union[Path, URL]) -> List[float]:
    """
    获取所有 I 帧的时间
    读取 packets 比 frames 快
    * 如果要存 cache ，key 的命名规则： xxx.mp4:{vindex}:i_frame_ts.json
    """
    try:
        # show_packets 比 show_frames 快得多，因为它只读头信息
        probe = ffmpeg.probe(
            str(video),
            select_streams='v:0',  # 默认使用第一条视频流
            skip_frame='nokey',  # 只读关键帧
            show_entries='packet=pts_time,flags',  # 读取包的时间戳和标记
            loglevel='error' if _IS_QUIET else 'info',  # 防止堵塞 stderr 管道
        )

        packets = probe.get('packets', [])
        # 在 packets 中，关键帧带有 'K' 标记 (flags="K__" 或包含 "K")
        timestamps = [
            float(p['pts_time'])
            for p in packets
            if 'K' in p.get('flags', '') and p.get('pts_time') is not None
        ]

        logger.success(f"成功提取到 {len(timestamps)} 个关键帧 (packets 模式)")
        return timestamps

    except ffmpeg.Error as e:
        # ffmpeg.run 报错时，错误信息在 e.stderr 中
        logger.error(f'FFmpeg 提取失败: {(e.stderr or b"").decode() or e}')
        return []

    except Exception as e:
        logger.exception(f'非预期异常: {e}')
        return []


@dataclass
class SegmentResult:
    segment: str
    start_time: float
    end_time: float


@time_it
def quick_segment(video: Union[Path, URL],
                  vindex: int,
                  output_dir: str,
                  start_time: float,
                  end_time: float,
                  i_frame_ts: list = None,
                  video_info: dict = None) -> SegmentResult:
    """
    快速裁切，为了让指定时间段内的 GOP 完整，往左右各扩到 I 帧位置，如左右没有 I 帧的情况，则使用端点
    示例： 用户指定 start_time 为第3s，往左查找第一个I帧是第2.5s，然后在 physical_start 第2.5s开始裁切，响应中的 start_time 指用户指定的时间点，相对与切出来的 segment 而言是第0.5s
    """
    if i_frame_ts is None:
        i_frame_ts = extract_i_frame_timestamps(video)

    # --- 物理切片的起点 (Seek Point) ---
    idx_s = bisect.bisect_right(i_frame_ts, start_time)
    physical_start = i_frame_ts[idx_s - 1] if idx_s > 0 else 0.0

    # --- 物理切片的终点 (End Point) ---
    idx_e = bisect.bisect_right(i_frame_ts, end_time)
    if idx_e < len(i_frame_ts):
        physical_end = i_frame_ts[idx_e]
    else:
        if video_info is None:
            video_info = extract_video_info(video)
        physical_end = video_info['duration']

    # --- 物理切片的长度 ---
    physical_duration = physical_end - physical_start
    output_path = os.path.join(output_dir, f"segment_{vindex}.mp4")

    try:
        # 使用 -ss (input 之前) + -t 的组合进行最快拷贝
        stream = (
            ffmpeg
            .input(str(video), ss=physical_start)
            .output(output_path,
                    t=physical_duration,
                    c='copy',
                    map=0,
                    ignore_editlist=1,
                    loglevel='error'
                    )
        )
        ffmpeg.run(stream, overwrite_output=True)

        # 【关键：相对时间转换】
        # 返回给 SegmentResult 的应该是相对于这个新片段 0 秒的位置
        rel_start = start_time - physical_start
        rel_end = end_time - physical_start

        logger.success(f"Segment {vindex} 成功: {physical_start:.2f}s -> {physical_end:.2f}s")

        return SegmentResult(
            segment=output_path,
            start_time=rel_start,
            end_time=rel_end
        )

    except ffmpeg.Error as e:
        logger.error(f'FFmpeg 切片失败: {(e.stderr or b"").decode() or e}')
        raise

    except Exception as e:
        logger.exception(f'非预期异常: {e}')
        raise

def build_atempo_filter(speed_ratio):
    if speed_ratio < 0.1:
        speed_ratio = 0.1
    elif speed_ratio > 100.0:
        speed_ratio = 100.0

    if 0.5 <= speed_ratio <= 2.0:
        return f"atempo={speed_ratio}"
    
    filters = []
    ratio = speed_ratio
    if ratio < 0.5:
        while ratio < 0.5:
            filters.append("atempo=0.5")
            ratio /= 0.5
        if ratio > 0:
            filters.append(f"atempo={ratio}")
    else:
        while ratio > 2.0:
            filters.append("atempo=2.0")
            ratio /= 2.0
        if ratio > 0:
            filters.append(f"atempo={ratio}")
            
    return ",".join(filters)

@dataclass
class SplitClip:
    main: str
    fade_in: Optional[str] = None
    fade_out: Optional[str] = None
    fade_in_duration: float = 0.0
    fade_out_duration: float = 0.0
    fade_in_reserve: float = 0.0
    fade_out_reserve: float = 0.0
    transition_caption: Optional[TransitionCaption] = None

@time_it
def split_normalize(video, duration, fade_in=0, fade_out=0, transition_reserve_factor=1.2) -> SplitClip:
    dir = os.path.dirname(video)
    vname = os.path.basename(video)
    log.info(
        f"{vname} split normalize, "
        f"fade_in={fade_in}, fade_out={fade_out}, "
        f"buffer_factor={transition_reserve_factor}"
    )

    fade_in_path = os.path.join(dir, f"fade_in_{vname}") if fade_in else None
    main_path = os.path.join(dir, f"middle_{vname}")
    fade_out_path = os.path.join(dir, f"fade_out_{vname}") if fade_out else None

    buffer_in = fade_in * transition_reserve_factor
    buffer_out = fade_out * transition_reserve_factor

    ffmpeg_cmd = ["ffmpeg", "-i", video]

    if fade_in:
        ffmpeg_cmd += ["-ss", "0", "-to", str(buffer_in), fade_in_path]
    ffmpeg_cmd += ["-ss", str(buffer_in), "-to", str(duration - buffer_out), main_path]
    if fade_out:
        ffmpeg_cmd += ["-ss", str(duration - buffer_out), "-to", str(duration), fade_out_path]

    ffmpeg_cmd.append("-y")
    run_ffmpeg_command(ffmpeg_cmd, video_name=vname)

    return SplitClip(
        main=main_path,
        fade_in=fade_in_path,
        fade_out=fade_out_path,
        fade_in_duration=buffer_in if fade_in else 0.0,
        fade_out_duration=buffer_out if fade_out else 0.0,
        fade_in_reserve=(buffer_in - fade_in) if fade_in else 0.0,
        fade_out_reserve=(buffer_out - fade_out) if fade_out else 0.0,
    )

@dataclass
class SegmentResult:
    segment: str
    start_time: float
    end_time: float

@time_it
def quick_segment(video, vindex, output_dir, start_time, end_time) -> SegmentResult:
    clip_point_list = []
    s = time.time()
    first_clip = max(10 * (start_time // 10 - 1), 0)
    second_clip = 10 * (2 + end_time // 10)
    log.info(f"first_clip: {first_clip}")
    if first_clip > 0:
        log.info(f"{type(first_clip)},{first_clip > 0} append {first_clip}")
        clip_point_list.append(str(first_clip))
    clip_point_list.append(str(second_clip))
    clip_str = ",".join(clip_point_list)
    segment = video

    segment_cmd = [
        'ffmpeg', "-ignore_editlist", "1",
        '-i', video,
        '-f', 'segment',
        '-segment_times', clip_str,
        '-reset_timestamps', '1',
        '-c', 'copy',
        f"{output_dir}segment_{vindex}_%03d.mp4"
    ]
    run_ffmpeg_command(segment_cmd)
    log.info(f"segmented to segment_{vindex}_000.mp4")

    if first_clip == 0:
        segment = f"{output_dir}segment_{vindex}_000.mp4"
        if os.path.exists(f"{output_dir}segment_{vindex}_001.mp4"):
            os.remove(f"{output_dir}segment_{vindex}_001.mp4")
    else:
        video_info = get_video_info(f"{output_dir}segment_{vindex}_000.mp4")
        w, h, d, r, f, codec = video_info.get_info()
        log.info(f"the duration of before segment_{vindex} is {d}")
        if start_time > d:
            start_time -= d
            end_time -= d
            log.info(f"start_time of segment_{vindex} become {start_time}, end time become {end_time}")
            segment = f"{output_dir}segment_{vindex}_001.mp4"
        if os.path.exists(f"{output_dir}segment_{vindex}_000.mp4"):
            os.remove(f"{output_dir}segment_{vindex}_000.mp4")
        if os.path.exists(f"{output_dir}segment_{vindex}_002.mp4"):
            os.remove(f"{output_dir}segment_{vindex}_002.mp4")
    log.info(f"segment takes {time.time() - s} seconds")

    return SegmentResult(segment=segment, start_time=start_time, end_time=end_time)

@time_it
def get_audio_info(audio_path_list: List[str]):
    durations = []
    for file_path in audio_path_list:
        if not file_path:
            durations.append(0)
            continue
        try:
            command = [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'json', file_path
            ]
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            info = json.loads(result.stdout.decode('utf-8'))
            duration = float(info['format']['duration'])
            durations.append(round(duration, 2))
        except Exception as e:
            print(f"Error getting duration for {file_path}: {str(e)}")
            durations.append(0)
    return durations

@time_it
def extract_audio(video_file: str, project_id: str = "test") -> str:
    abs_path = os.path.abspath(video_file)
    fn = os.path.splitext(os.path.basename(video_file))[0]
    output_dir = os.path.join(FINAL_DIR, project_id)
    os.makedirs(output_dir, exist_ok=True)
    output_audio = os.path.join(output_dir, f"{fn}.wav")

    check_audio_cmd = [
        "ffprobe", "-v", "error", "-select_streams", "a",
        "-show_entries", "stream=index", "-of", "csv=p=0", abs_path,
    ]
    try:
        result = subprocess.run(check_audio_cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise ServiceException(466, "检查是否有音频流失败", data=e.stderr)

    if not result.stdout.strip():
        log.info(f"{video_file} does not contain audio stream")
        return ""

    ffmpeg_cmd = [
        "ffmpeg", "-i", abs_path, "-vn",
        "-acodec", "pcm_s16le", "-f", "wav", "-threads", "1", output_audio, "-y",
    ]
    run_ffmpeg_command(ffmpeg_cmd, video_name=video_file)
    return output_audio

@time_it
def concatenate_wavs(input_files: List[str], project_id: str = "test", need_pause=True) -> str:
    output_file_prefix = "/".join([FINAL_DIR, project_id])
    os.makedirs(output_file_prefix, exist_ok=True)
    source_txt_path = f'file_list_{project_id}.txt'
    output_file = f"{output_file_prefix}/full_{project_id}.wav"
    log.info(f"exported to {output_file}")
    if not input_files:
        return ""

    with open(source_txt_path, 'w') as f:
        for idx, file in enumerate(input_files):
            if not file: continue
            f.write(f"file '{file}'\n")
            if need_pause and idx != len(input_files) - 1:
                f.write(f"file 'silence1.wav'\n")

    try:
        command = [
            'ffmpeg', '-f', 'concat', '-safe', '0',
            '-i', source_txt_path, '-c', 'copy', output_file
        ]
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return output_file
    except subprocess.CalledProcessError as e:
        print(f"Error concatenating WAV files: {e.stderr.decode('utf-8')}")
        return ""
    finally:
        if os.path.exists(source_txt_path):
            os.remove(source_txt_path)

@time_it
async def mute_audio(audio: str, project_id: str = "test") -> str:
    if not audio:
        return ""
    output_file = os.path.join(FINAL_DIR, project_id, f"muted_{os.path.basename(audio)}")
    command = [
        'ffmpeg', '-i', audio, '-af', 'volume=0', '-y', output_file
    ]
    await asyncio.to_thread(run_ffmpeg_command, command, video_name=audio)
    return output_file
