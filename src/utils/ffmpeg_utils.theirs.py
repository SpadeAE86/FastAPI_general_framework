"""
ffmpeg 工具
# todo 直接进显存


1. 视频信息提取：强烈建议引入 MediaInfo
虽然你已经写了 PyAV 的提取逻辑，但正如你之前遇到的 0xC0000005 崩溃，PyAV 在处理破损视频或特定编码时极易内存溢出。

为什么用 MediaInfo： 它对各种奇葩格式（如带旋转角度的手机视频、复杂的 HDR 信息）支持最稳。

建议： 用 pymediainfo 获取基础参数（分辨率、码率、时长），仅在需要获取“视频流第一帧图像”这类操作时才动用 PyAV。

2. 音视频提取、裁切、拼接：ffmpeg-python 是主力
理由： 裁切和拼接涉及到“流拷贝（stream copy）”或“重编码”。

ffmpeg-python 优势： 对于“拼接多个视频”或“将音频合成到视频”，FFmpeg 的 filter_complex 逻辑极其强大。用 PyAV 去写拼接逻辑需要手动管理 Timestamp（时间戳）同步，代码量会多出 10 倍且极易音画不同步。

3. 字幕绘制：ffmpeg-python (drawtext/subtitles)
建议： 直接调用 FFmpeg 的滤镜。PyAV 并不擅长图形渲染，它只是搬运像素数据的。

4. 逐帧处理（如果需要）：PyAV
场景： 如果你需要“读取每一帧并用 AI 进行人脸识别”再写回视频，PyAV 是唯一的选择，因为它能让你在内存中直接拿到 numpy 数组，比 ffmpeg-python 频繁开关管道快得多。

"""
import io
import os
import tempfile
import json
import ffmpeg
from functools import lru_cache
from pathlib import Path
from json.decoder import JSONDecodeError
from typing import Union, Generator, Iterable
from pymediainfo import MediaInfo

from config.config import MY_CONFIG, ENV, TEMP_DIR
from utils.log_utils import logger, time_it, LOG_LEVEL
from utils.cmd_utils import run_command


@lru_cache(maxsize=1)
def get_hw_capabilities():
    """
    同步获取硬件信息
    todo 无实际作用。检查出来的只是是否有接口支持，并不代表实际硬件支持
    """
    _, hwaccels, _ = run_command(['ffmpeg', '-hwaccels'], timeout=5)
    _, decoders, _ = run_command(['ffmpeg', '-decoders'], timeout=5)
    _, encoders, _ = run_command(['ffmpeg', '-encoders'], timeout=5)
    return hwaccels, decoders, encoders


def get_hw_config(decoder_pref: str = None, encoder_pref: str = None) -> dict:
    """
    硬件/软件编解码配置映射
    :param decoder_pref: qsv, cuda, amf, cpu
    :param encoder_pref: qsv, cuda, amf, cpu
    """

    if decoder_pref is None:
        decoder_pref = _DECODER
    if encoder_pref is None:
        encoder_pref = _ENCODER

    # 解码配置映射 (用于 .input 参数)
    # hwaccel: 硬件加速引擎名
    # v_decoder: 显式指定的解码器名 (某些格式下比自动选择更稳)
    decoders_map = {
        'qsv': {'hwaccel': 'qsv', 'v_decoder': 'h264_qsv'},
        'cuda': {'hwaccel': 'cuda', 'v_decoder': 'h264_cuvid'},
        'amf': {'hwaccel': 'd3d11va', 'v_decoder': 'h264_amf'},  # AMF 通常配合 d3d11va 加速
        'cpu': {'hwaccel': None, 'v_decoder': 'h264'}  # 纯软件解码
    }

    # 编码配置映射 (用于 .output 参数)
    encoders_map = {
        'qsv': {'v_encoder': 'h264_qsv'},
        'cuda': {'v_encoder': 'h264_nvenc'},
        'amf': {'v_encoder': 'h264_amf'},
        'cpu': {'v_encoder': 'libx264'}  # 经典的 CPU 软件编码器
    }

    # 安全检查：如果请求的 key 不在 map 中，默认回退到 cpu
    decoder_config = decoders_map.get(decoder_pref.lower(), decoders_map['cpu'])
    encoder_config = encoders_map.get(encoder_pref.lower(), encoders_map['cpu'])

    return {
        'hwaccel': decoder_config['hwaccel'],
        'v_decoder': decoder_config['v_decoder'],
        'v_encoder': encoder_config['v_encoder']
    }


@time_it
def has_audio_stream(video: Union[Path, io.BufferedIOBase, bytes], use_mediainfo: bool = True) -> bool:
    """
    检查是否有音频流
    :param video:
    :param use_mediainfo:
    :return:
    """
    if use_mediainfo:
        if isinstance(video, bytes):
            # MediaInfo 不收 bytes，必须包一层 BytesIO
            input_data = io.BytesIO(video)
        else:
            input_data = video

        media_info = MediaInfo.parse(input_data)
        for track in media_info.tracks:
            if track.track_type == 'Audio':
                return True

        return False

    logger.warning('以下 ffprobe 模式 已弃用，请改用 mediainfo 模式。原因：慢')

    # 1. 构造基础命令 (如果是 bytes，-i 必须是 pipe:0)
    is_video_bytes = isinstance(video, bytes)

    cmd = [
        'ffprobe',  # FFprobe 可执行文件路径
        '-show_streams',  # 【核心输出】显示视频文件中所有流的详细信息（编码、分辨率、码率等）
        # '-select_streams', 'a',  # 【流筛选】仅处理音频流(a)。若注释掉，则输出包括视频(v)、音频(a)、数据(d)在内的所有流
        '-of', 'json',  # 【输出格式】指定输出为标准 JSON 格式，便于 Python 使用 json.loads() 解析
        '-v', 'error',  # 【日志级别】只显示错误信息。隐藏 Banner 和警告，确保 stdout 只有纯净的 JSON 结果
        # '-probesize', '5000000',  # 【探测阈值】设置读取多少字节来分析格式。对于 Pipe 模式，若 moov 在尾部，此值需设大
        # '-analyzeduration', '1000000',  # 【分析时长】设置分析流信息的时间上限(微秒)。1000000 = 1秒
        '-i', 'pipe:0' if is_video_bytes else str(video)
        # 【输入源内容】# pipe:0 -> 从标准输入(stdin)读取 bytes 数据（避开 Windows 命令行长度限制）# video  -> 直接读取本地文件路径（支持 Seek 随机访问，效率最高）
    ]

    # 2. 调用通用的 run_command
    code, stdout, stderr = run_command(cmd, input_data=video if is_video_bytes else None, timeout=30)

    # 3. 解析结果
    if code != 0:
        logger.error(f'探测失败，进程退出码: {code} | 错误详情: {stderr}')
        return False
    if not stdout or not stdout.strip():
        logger.error('FFprobe 未返回任何输出内容')
        return False
    try:
        data = json.loads(stdout)
        streams = data.get('streams', [])
        logger.debug(f'探测到 {len(streams)} 个流: {[s.get('codec_type') for s in streams]}')
        return any(s.get('codec_type') == 'audio' for s in streams)
    except JSONDecodeError as e:
        logger.error(f'JSON 解析失败：输出内容不是合法的 JSON 格式')
        logger.error(f'原始输出内容前100位: {stdout[:100]}')
        logger.error(f'报错位置: 行 {e.lineno}, 列 {e.colno}')
        return False
    except KeyError:
        logger.error('JSON 结构异常：未找到 streams 节点')
        return False
    except Exception as e:
        logger.exception(f'解析 FFprobe 结果时发生非预期异常: {e}')
        return False


@time_it
def extract_audio_from_video(
        video: Path,
        as_path: bool = False,
        audio: Path = None,
        as_gen: bool = False
) -> Union[Path, bytes, Generator[bytes, None, None], None]:
    """
    从视频中提取音频 (WAV PCM 44100Hz 16bit Stereo)
    todo 音频数据（bytes）和音频数据（generator）不含头信息
    :param video: 输入视频（Path）
    :param as_path: 为 True 时返回 Path 对象
    :param audio: 只有当 as_path=True 时有效，指定输出路径；若未提供则生成临时文件（wav格式，后缀必须.wav）
    :param as_gen: 返回生成器
    :return: 文件路径（Path）、音频数据（bytes）、音频数据（generator），失败返回 None
    """
    # as 参数互斥，as_path 优先
    if as_path:
        as_gen = False

    # 临时文件清理标记
    is_temp_file = False

    # ffmpeg input
    input_source = str(video)
    input_args = {
        'vn': None,  # 禁用视频流
        'sn': None,  # 禁用字幕流
        'dn': None,  # 禁用数据流
        'fflags': '+fastseek+nobuffer'  # fastseek: 快速定位；nobuffer: 减少内存读写缓冲延迟
    }

    # ffmpeg output
    if as_path:
        output_format = 'wav'  # 文件模式使用 wav
        if audio:
            # 检查后缀，使用用户指定的路径，确保父目录存在
            assert audio.suffix == f'.{output_format}'
            output_dest = str(audio)
            Path(output_dest).parent.mkdir(parents=True, exist_ok=True)
        else:
            # 创建临时文件，关闭文件句柄，只留路径字符串
            fd, output_dest = tempfile.mkstemp(suffix=f'.{output_format}', dir=TEMP_DIR)
            os.close(fd)
            is_temp_file = True
    else:
        output_format = 's16le'  # stdout 使用 s16le 流
        output_dest = 'pipe:'
    output_args = {
        'loglevel': 'error' if _IS_QUIET else 'info',  # 防止堵塞 stderr 管道
        'format': output_format,  # 封装格式：指定输出为 WAV 容器。WAV 是无损格式，适合中间处理，兼容性极强。
        'acodec': 'pcm_s16le',
        # 编码器：使用 pcm_s16le。# pcm: 脉冲编码调制（无损原始数据）。 # s16: 16位有符号整数（每个采样点占用 2 字节，动态范围约 96dB）。# le: 小端字节序（Little Endian，Windows/Linux 系统的标准存储方式）。
        'ar': '44100',  # 采样率：44100Hz (44.1kHz)。# 这是 CD 标准采样率。根据奈奎斯特采样定理，它可以完美还原最高 22.05kHz 的频率（涵盖人耳听觉极限）。
        'ac': 2,  # 声道数：2 (Stereo 立体声)。# 1 代表单声道 (Mono)，2 代表左右双声道。
        'threads': 1,  # 减少上下文切换开销
        'map_metadata': -1,  # 丢弃元数据（封面图、歌词等），进一步加快速度
    }

    # 构建、执行
    try:
        # 构建并异步执行
        process = (
            ffmpeg
            .input(input_source, **input_args)
            .output(output_dest, **output_args)
            .run_async(
                pipe_stdout=not as_path,
                # pipe_stderr=False, # 默认 False
                quiet=_IS_QUIET,
                overwrite_output=True,
            )
        )

        # 模式 3: 返回生成器 (Generator)
        if as_gen:
            def _generator():
                try:
                    while True:
                        # 核心读取点
                        chunk = process.stdout.read(CHUNK_SIZE)
                        if not chunk:
                            # 检查是否是因为报错而停止
                            if process.poll() is not None and process.returncode != 0:
                                logger.error(f'提取进程异常退出，Code: {process.returncode}')
                            break

                        # 只要这里执行了，save 函数就会打印 Feeding chunk...
                        yield chunk

                    process.wait()
                finally:
                    if process.stdout: process.stdout.close()
                    if process.stderr: process.stderr.close()
                    if process.poll() is None: process.kill()

            logger.success(f'音频提取成功 -> generator')
            return _generator()

        # 模式 2: 返回路径
        if as_path:
            process.wait()
            logger.success(f'音频提取成功 -> {output_dest}')
            return Path(output_dest)

        # 模式 1: 返回全量 Bytes (兼容旧逻辑，但大文件慎用)
        out, _ = process.communicate()
        logger.success(f'音频提取成功 -> bytes')
        return out

    except ffmpeg.Error as e:
        logger.error(f'FFmpeg 提取失败: {e}')

        # 仅在出错且是自动生成的临时文件时进行清理
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
    """
    将 Raw PCM 数据封装为标准 WAV 文件，支持 bytes 或 生成器
    """
    if not data:
        logger.warning('音频数据为空，跳过保存')
        return False

    process = None
    try:
        process = (
            ffmpeg
            .input('pipe:', **{
                'format': 's16le',  # 封装格式：指定输出为 WAV 容器。WAV 是无损格式，适合中间处理，兼容性极强。
                'ar': '44100',  # 采样率：44100Hz (44.1kHz)。# 这是 CD 标准采样率。根据奈奎斯特采样定理，它可以完美还原最高 22.05kHz 的频率（涵盖人耳听觉极限）。
                'ac': 2,  # 声道数：2 (Stereo 立体声)。# 1 代表单声道 (Mono)，2 代表左右双声道。
            })
            .output(str(audio), **{
                'loglevel': 'error' if _IS_QUIET else 'info',  # 防止堵塞 stderr 管道
                'acodec': 'copy',  # 封装格式：指定输出为 WAV 容器。WAV 是无损格式，适合中间处理，兼容性极强。
                'threads': 1,  # 减少上下文切换开销
            })
            .overwrite_output()
            .run_async(
                pipe_stdin=True,
                # pipe_stdout=False,
                # pipe_stderr=False,
                quiet=_IS_QUIET,
                overwrite_output=True,
            )
        )

        # 统一迭代器逻辑
        if isinstance(data, (bytes, bytearray)):
            # 将 bytes 包装成一个切片生成器
            data_iter = (data[i: i + CHUNK_SIZE] for i in range(0, len(data), CHUNK_SIZE))
        else:
            data_iter = data

        # 逐块写入 stdin
        for chunk in data_iter:
            if chunk:
                process.stdin.write(chunk)

        # 必须关闭管道，FFmpeg 才会收到 EOF (文件结束符) 并正常关闭文件头
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
    """
    提取视频流信息
    默认提取第一条视频流的
    todo 由于 mpc 出来的并不能确保 pix_fmt=yuv420p ，所以在最终合并时需要强制统一像素格式：使用 .filter('format', 'yuv420p')。
    :param video:
    :param use_mediainfo:
    :return:
    """

    if use_mediainfo:
        # 处理输入源
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
            """
            旋转角度统一成 ffprobe 样式
            """
            if rotation_value == 0:
                ffmpeg_style_rotation = 0
            else:
                # 逻辑：MediaInfo 90 -> FFmpeg -90; MediaInfo 270 -> FFmpeg -270 (或 90)
                # 为了完全对齐 ffprobe 的输出习惯：
                # 我们先取负，然后归一化到 (-360, 360) 之间
                ffmpeg_style_rotation = -rotation_value

                # 如果你希望严格像 ffprobe 那样显示 -90 而不是 270：
                if ffmpeg_style_rotation <= -360:
                    ffmpeg_style_rotation %= 360
            return ffmpeg_style_rotation

        def _map_to_ffmpeg_pix_fmt(track) -> str:
            """
            像素格式映射
            :param track:
            :return:
            """
            chroma = getattr(track, 'chroma_subsampling', '4:2:0').replace(':', '')
            depth = int(getattr(track, 'bit_depth', 8))

            # 常见的像素格式组合
            if depth == 8:
                return f'yuv{chroma}p'
            elif depth == 10:
                # iPhone HDR 视频通常映射为 yuv420p10le
                return f'yuv{chroma}p10le'
            elif depth == 12:
                return f'yuv{chroma}p12le'

            return f'yuv{chroma}p'

        # 1. 编码名称映射 (FFmpeg 兼容)
        def _map_to_ffmpeg_codec(track_format) -> str:
            """
            编码名称映射
            :param track_format:
            :return:
            """
            codec_map = {
                'AVC': 'h264',
                'HEVC': 'hevc',
                'MPEG-4 Visual': 'mpeg4',
                'MPEG Video': 'mpeg2video',
                'ProRes': 'prores'
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
        # 定位视频流
        video_stream = next((s for s in full_info.get('streams', []) if s.get('codec_type') == 'video'), {})
        if not video_stream:
            return None

        # 获取容器格式信息
        format_info = full_info.get('format', {})

        # --- 核心属性提取 ---

        # 宽高：直接取流中的像素值
        width = int(video_stream.get('width', 0))
        height = int(video_stream.get('height', 0))

        # 时长：优先取 format 里的 duration，这是最准确的整片时长
        duration = float(format_info.get('duration', 0))

        # 旋转角度：如 -90
        rotation = float(([_['rotation'] for _ in video_stream.get('side_data_list', []) if 'rotation' in _] or [0])[0])

        # 像素格式：如 'yuv420p'
        pix_fmt = video_stream.get('pix_fmt', '')

        # 编码名称：如 'h264'
        codec_name = video_stream.get('codec_name', '')

        return {
            "width": width,
            "height": height,
            "duration": duration,
            "rotation": rotation,
            "pix_fmt": pix_fmt,
            "codec_name": codec_name,
        }

    return _extract_from_probe(full_info)

# todo
# # =========================
# # I 帧快速裁切策略（heuristic）
# # 使用场景：
# # - 用户上传【超长视频】，但只需要其中一小段
# # - 直接从原视频精确裁切会导致大量无用解码
# # - I 帧分布有时非常稀疏，seek 不准、解码成本高
# #
# # 核心思路：
# # 1. 仅在「视频足够长 && 所需片段相对很小」时启用
# # 2. 利用 ffmpeg 的 segment + copy：
# #    - 只在 I 帧附近切
# #    - 生成更短的视频文件
# #    - 后续精确裁切只在短视频上进行
# # =========================
# def quick_segment(video, vindex, output_dir, start_time, end_time) -> SegmentResult:
#     """
#     利用 ffmpeg segment + copy 做 I 帧级别的快速裁切
#
#     目标：
#     - 避免从视频开头解码到 start_time
#     - 只保留「可能包含目标片段」的最小视频范围
#     """
#     clip_point_list = []
#     s = time.time()
#     # =========================
#     # 计算粗裁切点（10 秒粒度）
#     #
#     # first_clip:
#     #   - 往 start_time 前多留 10 秒
#     #   - 防止 I 帧刚好在边界之外
#     #
#     # second_clip:
#     #   - end_time 后多留 20 秒
#     #   - 给后续精裁留 buffer
#     # =========================
#     first_clip = max(10 * (start_time // 10 - 1), 0)
#     second_clip = 10 * (2 + end_time // 10)
#     log.info(f"first_clip: {first_clip}")
#     if first_clip > 0:
#         log.info(f"{type(first_clip)},{first_clip > 0} append {first_clip}")
#         clip_point_list.append(str(first_clip))
#     clip_point_list.append(str(second_clip))
#     clip_str = ",".join(clip_point_list)
#     segment = video
#     # =========================
#     # ffmpeg segment 命令说明
#     #
#     # -ignore_editlist 1
#     #   → 忽略 mp4 内部编辑列表，避免时间轴错乱
#     #
#     # -f segment
#     #   → 按时间点切成多个文件
#     #
#     # -segment_times
#     #   → 指定切点（只在 I 帧切）
#     #
#     # -c copy
#     #   → 不重新编码，速度极快
#     # =========================
#     segment_cmd = [
#         'ffmpeg', "-ignore_editlist", "1",
#         '-i', video,
#         '-f', 'segment',
#         '-segment_times', clip_str,
#         '-reset_timestamps', '1',
#         '-c', 'copy',
#         f"{output_dir}segment_{vindex}_%03d.mp4"
#     ]
#     run_ffmpeg_command(segment_cmd)
#     log.info(f"segmented to segment_{vindex}_000.mp4")
#     if first_clip == 0:
#         # =========================
#         # 情况一：first_clip == 0
#         # → 说明目标就在视频前部
#         # → 直接使用 000 号片段
#         # =========================
#         segment = f"{output_dir}segment_{vindex}_000.mp4"
#         if os.path.exists(f"{output_dir}segment_{vindex}_001.mp4"):
#             os.remove(f"{output_dir}segment_{vindex}_001.mp4")
#     else:
#         # =========================
#         # 情况二：first_clip > 0
#         # → 生成的 000 是「目标前的视频」
#         # → 目标可能在 001 中
#         # =========================
#
#         video_info = get_video_info(f"{output_dir}segment_{vindex}_000.mp4")
#         w, h, d, r, f, codec = video_info.get_info()
#         log.info(f"the duration of before segment_{vindex} is {d}")
#         if start_time > d:
#             start_time -= d
#             end_time -= d
#             log.info(f"start_time of segment_{vindex} become {start_time}, end time become {end_time}")
#             segment = f"{output_dir}segment_{vindex}_001.mp4"
#         if os.path.exists(f"{output_dir}segment_{vindex}_000.mp4"):
#             os.remove(f"{output_dir}segment_{vindex}_000.mp4")
#         if os.path.exists(f"{output_dir}segment_{vindex}_002.mp4"):
#             os.remove(f"{output_dir}segment_{vindex}_002.mp4")
#     log.info(f"segment takes {time.time() - s} seconds")
#
#     return SegmentResult(segment=segment,
#                          start_time=start_time,
#                          end_time=end_time)
#

# --- 配置 ---
_DECODER = MY_CONFIG['hw'][ENV]['decoder']
_ENCODER = MY_CONFIG['hw'][ENV]['encoder']

# --- 流分块大小 ---
CHUNK_SIZE: int = 4 * 1024 * 1024  # 4M

# --- ffmpeg 是否不输出控制台日志 ---
_IS_QUIET: bool = True if logger.level(LOG_LEVEL).no > logger.level('TRACE').no else False  # info 以下都打印

# @time_it
# def extract_xxx(
#         video: Path,
#         decoder_pref: str = 'cpu',
#         encoder_pref: str = 'cpu',
#         as_path: bool = False,
#         audio: Path = None,
#         as_gen: bool = False
# ) -> Union[Path, bytes, Generator[bytes, None, None], None]:
#     """
#     从视频中提取音频 (WAV PCM 44100Hz 16bit Stereo)
#
#     # todo 输出音频流不含头信息
#
#     :param video: 输入视频（Path）
#     :param decoder_pref:
#     :param encoder_pref:
#     :param as_path: 为 True 时返回 Path 对象，为 False 返回 bytes
#     :param audio: 只有当 as_path=True 时有效，指定输出路径；若未提供则生成临时文件
#     :param as_gen: 返回生成器
#     :return: 文件路径（Path）、音频数据（bytes）、音频数据（generator），失败返回 None
#     """
#     # as 参数互斥，as_path 优先
#     if as_path:
#         as_gen = False
#
#     # hw
#     hw_config = get_hw_config(decoder_pref, encoder_pref)
#
#     # 临时文件清理标记
#     is_temp_file = False
#
#     # ffmpeg input
#     input_source = str(video)
#     input_args = {
#         'vn': None,  # 禁用视频流
#         'sn': None,  # 禁用字幕流
#         'dn': None,  # 禁用数据流
#         'fflags': '+fastseek+nobuffer'  # fastseek: 快速定位；nobuffer: 减少内存读写缓冲延迟
#     }
#     if hw_config.get('hwaccel'):
#         input_args['hwaccel'] = hw_config['hwaccel']
#
#     # ffmpeg output
#     output_format = 'wav'
#     if as_path:
#         if audio:
#             # 使用用户指定的路径，确保父目录存在
#             output_dest = str(audio)
#             Path(output_dest).parent.mkdir(parents=True, exist_ok=True)
#         else:
#             # 创建临时文件
#             fd, temp_path = tempfile.mkstemp(suffix='.wav', dir=TEMP_DIR)
#             os.close(fd)
#             output_dest = temp_path
#             is_temp_file = True
#     else:
#         output_format = 's16le'
#         output_dest = 'pipe:'
#     output_args = {
#         'format': output_format,  # 封装格式：指定输出为 WAV 容器。WAV 是无损格式，适合中间处理，兼容性极强。
#         'acodec': 'pcm_s16le',
#         # 编码器：使用 pcm_s16le。# pcm: 脉冲编码调制（无损原始数据）。 # s16: 16位有符号整数（每个采样点占用 2 字节，动态范围约 96dB）。# le: 小端字节序（Little Endian，Windows/Linux 系统的标准存储方式）。
#         'ar': '44100',  # 采样率：44100Hz (44.1kHz)。# 这是 CD 标准采样率。根据奈奎斯特采样定理，它可以完美还原最高 22.05kHz 的频率（涵盖人耳听觉极限）。
#         'ac': 2,  # 声道数：2 (Stereo 立体声)。# 1 代表单声道 (Mono)，2 代表左右双声道。
#         'threads': 1,  # 减少上下文切换开销
#         'map_metadata': -1,  # 丢弃元数据（封面图、歌词等），进一步加快速度
#     }
#
#     # 构建、执行
#     try:
#         # 构建并异步执行
#         process = (
#             ffmpeg
#             .input(input_source, **input_args)
#             .output(output_dest, **output_args)
#             .run_async(
#                 pipe_stdout=not as_path,
#                 pipe_stderr=False,
#                 quiet=False,
#                 overwrite_output=True,
#             )
#         )
#
#         # 模式 3: 返回生成器 (Generator)
#         if as_gen:
#             def _generator():
#                 try:
#                     while True:
#                         # 核心读取点
#                         chunk = process.stdout.read(CHUNK_SIZE)
#                         if not chunk:
#                             # 检查是否是因为报错而停止
#                             if process.poll() is not None and process.returncode != 0:
#                                 logger.error(f"提取进程异常退出，Code: {process.returncode}")
#                             break
#
#                         # 只要这里执行了，save 函数就会打印 Feeding chunk...
#                         yield chunk
#
#                     process.wait()
#                 finally:
#                     if process.stdout: process.stdout.close()
#                     if process.stderr: process.stderr.close()
#                     if process.poll() is None: process.kill()
#
#             logger.success(f'音频提取成功 -> generator')
#             return _generator()
#
#         # 模式 2: 返回路径
#         if as_path:
#             process.wait()
#             logger.success(f'音频提取成功 -> {output_dest}')
#             return Path(output_dest)
#
#         # 模式 1: 返回全量 Bytes (兼容旧逻辑，但大文件慎用)
#         out, _ = process.communicate()
#         logger.success(f'音频提取成功 -> bytes')
#         return out
#
#     except ffmpeg.Error as e:
#         logger.error(f'FFmpeg 提取失败: {e}')
#
#         # 仅在出错且是自动生成的临时文件时进行清理
#         if is_temp_file and output_dest and os.path.exists(output_dest):
#             os.remove(output_dest)
#         return None
#
#     except Exception as e:
#         logger.exception(f'提取音频时发生非预期异常: {e}')
#         if is_temp_file and output_dest and os.path.exists(output_dest):
#             os.remove(output_dest)
#         return None


if __name__ == '__main__':
    # ----------------------------------------------------
    # 测试
    # ----------------------------------------------------
    from pprint import pprint

    # # 测试获取硬件信息
    # print(f'{get_hw_capabilities() = }')

    # # 测试编解码器
    # print(f'{get_hw_config() = }')

    # 测试检查是否有音频流
    for video in [
        TEMP_DIR / 'final-1773311230041.mp4',
        # TEMP_DIR / 'IMG_7943.MOV',
        # Path('C:/wsn_code/freeu/aigc/temp/03-4K.高码率.mp4'),
    ]:
        # # 测试检查是否有音频流
        # print(f'{has_audio_stream(video) = }')
        # with open(video, 'rb') as f:
        #     print(f'{has_audio_stream(f) = }')
        # with open(video, 'rb') as f:
        #     print(f'{has_audio_stream(f.read()) = }')

        # # 测试提取音频
        # print(f'{extract_audio_from_video(video) = }')
        # print(f'{extract_audio_from_video(video, as_path=True) = }')
        # print(f'{extract_audio_from_video(video, as_path=True,audio=TEMP_DIR / '111.wav') = }')
        # print(f'{extract_audio_from_video(video, as_gen=True) = }')

        # # 测试保存提取出来的音频流
        # print(f'{extract_audio_from_video(video, as_path=True,audio=TEMP_DIR / 'as_path.wav') = }') # 2.91s
        # print(f'{save_data_to_audio(extract_audio_from_video(video), TEMP_DIR / 'from_bytes.wav') = }')  # 5.50s
        # print(f'{save_data_to_audio(extract_audio_from_video(video,as_gen=True), TEMP_DIR / 'from_gen.wav') = }')  # 2.94s

        # 测试提取视频信息
        print(f'{extract_video_info(video) = }')
        print(f'{extract_video_info(video, False) = }')
        # with open(video, 'rb') as f:
        #     print(f'{extract_video_info(f) = }')
        # with open(video, 'rb') as f:
        #     print(f'{extract_video_info(f.read()) = }')
