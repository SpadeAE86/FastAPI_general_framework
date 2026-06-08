import argparse
import asyncio
import json
import os
import re
import time
from asyncio import Semaphore
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    import sys
    from pathlib import Path as _Path

    sys.path.append(str(_Path(__file__).resolve().parents[1]))

from config.config import ENV, my_config
from exceptions.ServiceException import ServiceException
from models.pydantic_models.request.volcovoice_request import Volcovoice_VO, character_options
from models.pydantic_models.response.volcovoice_response import (
    VolcovoiceDetail,
    VolcovoiceObject,
    VolcovoiceResponse,
)
from utils.ffmpeg_utils import get_audio_info, mute_audio
from utils.general_utils import delayed_delete, random_with_system_time, run_ffmpeg_command
from utils.log_utils import logger as log
from utils.obs_utils import upload_audio
from utils.volcano_utils import VolcanoWordTimestamp, parse_frontend_words, volcano_generate_voice

try:
    from utils.post_utils import post
except ImportError:
    post = None


volcovoice_semaphore = Semaphore(
    max(1, int(my_config.get("audio", {}).get("Volcano", {}).get("max_concurrency", 20)))
)

STRONG_PUNCTUATION = "\u3002\uff01\uff1f!?\uff1b;"
COMMA_PUNCTUATION = "\uff0c,\u3001\uff1a:"
COMMA_SOFT_MIN_CHARS = 4
COMMA_SOFT_MIN_DURATION_MS = 2200
COMMA_SOFT_MIN_PAUSE_MS = 0
COMMA_HARD_MIN_CHARS = 10
COMMA_HARD_MIN_DURATION_MS = 3600
BOUNDARY_PADDING_MS = 40
OUTPUT_AUDIO_FORMATS = {
    "wav": {"suffix": ".wav", "codec": "pcm_s16le"},
    "mp3": {"suffix": ".mp3", "codec": "libmp3lame"},
}


def _ensure_ascii_filename(text: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_.-]+", "_", text).strip("_")
    return sanitized or "segment"


def _write_json(path: str, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _normalize_output_format(file_format: str) -> str:
    normalized = (file_format or "wav").lower()
    if normalized not in OUTPUT_AUDIO_FORMATS:
        raise ServiceException(code=450, message="file_format must be one of: wav, mp3")
    return normalized


def _output_suffix(file_format: str) -> str:
    return OUTPUT_AUDIO_FORMATS[_normalize_output_format(file_format)]["suffix"]


def _ffmpeg_audio_codec(file_format: str) -> str:
    return OUTPUT_AUDIO_FORMATS[_normalize_output_format(file_format)]["codec"]


def _strip_ending_punctuation(text: str) -> str:
    text = text.rstrip()
    if not text:
        return text
    
    # Check if the text ends with ellipses or dashes
    if text.endswith("...") or text.endswith("……") or text.endswith("——") or text.endswith("-"):
        return text
        
    to_remove = "，。、；：,.;: "
    while text and text[-1] in to_remove:
        if text.endswith("...") or text.endswith("……") or text.endswith("——") or text.endswith("-"):
            break
        text = text[:-1]
    return text


def _is_strong_boundary(word: str) -> bool:
    return bool(word) and word[-1] in STRONG_PUNCTUATION


def _is_comma_boundary(word: str) -> bool:
    return bool(word) and word[-1] in COMMA_PUNCTUATION


def _build_segments_from_words(words: list[VolcanoWordTimestamp]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not words:
        return [], []

    decisions: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []
    current_words: list[VolcanoWordTimestamp] = []

    def flush_segment(boundary_reason: str, next_start_ms: float | None) -> None:
        nonlocal current_words
        if not current_words:
            return
        start_ms = float(current_words[0].start_time)
        end_ms = float(current_words[-1].end_time)
        caption_text = "".join(word.word for word in current_words)
        caption_text = _strip_ending_punctuation(caption_text)
        pause_ms = max(0.0, (next_start_ms - end_ms) if next_start_ms is not None else 0.0)
        segments.append(
            {
                "caption_text": caption_text,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": max(0.0, end_ms - start_ms),
                "pause_ms": pause_ms,
                "boundary_reason": boundary_reason,
                "word_count": len(current_words),
            }
        )
        current_words = []

    for idx, word in enumerate(words):
        current_words.append(word)
        next_word = words[idx + 1] if idx + 1 < len(words) else None
        next_start_ms = float(next_word.start_time) if next_word else None
        current_text = "".join(item.word for item in current_words)
        current_duration_ms = float(current_words[-1].end_time - current_words[0].start_time)
        pause_ms = max(0.0, (next_start_ms - word.end_time) if next_start_ms is not None else 0.0)

        if _is_strong_boundary(word.word):
            decisions.append(
                {
                    "token": word.word,
                    "decision": "split",
                    "reason": ["strong_punctuation"],
                    "current_chars": len(current_text),
                    "current_duration_ms": current_duration_ms,
                    "pause_ms": pause_ms,
                }
            )
            flush_segment("strong_punctuation", next_start_ms)
            continue

        if _is_comma_boundary(word.word):
            soft_ready = (
                len(current_text) >= COMMA_SOFT_MIN_CHARS
                or current_duration_ms >= COMMA_SOFT_MIN_DURATION_MS
            )
            hard_ready = (
                len(current_text) >= COMMA_HARD_MIN_CHARS
                or current_duration_ms >= COMMA_HARD_MIN_DURATION_MS
            )
            should_split = hard_ready or (soft_ready and pause_ms >= COMMA_SOFT_MIN_PAUSE_MS)
            reason: list[str] = []
            if hard_ready:
                reason.append("hard_length_threshold")
            if soft_ready and pause_ms >= COMMA_SOFT_MIN_PAUSE_MS:
                reason.append("soft_length_plus_pause")
            if not reason:
                reason.append("keep_short_clause")
            decisions.append(
                {
                    "token": word.word,
                    "decision": "split" if should_split else "keep",
                    "reason": reason,
                    "current_chars": len(current_text),
                    "current_duration_ms": current_duration_ms,
                    "pause_ms": pause_ms,
                }
            )
            if should_split:
                flush_segment("comma_rule", next_start_ms)
                continue

    flush_segment("tail", None)
    return segments, decisions


def _trim_audio_segment(source_audio: str, output_audio: str, start_ms: float, end_ms: float, file_format: str) -> str:
    start_sec = max(0.0, (start_ms - BOUNDARY_PADDING_MS) / 1000.0)
    end_sec = max(start_sec + 0.05, (end_ms + BOUNDARY_PADDING_MS) / 1000.0)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        source_audio,
        "-ss",
        f"{start_sec:.3f}",
        "-to",
        f"{end_sec:.3f}",
        "-c:a",
        _ffmpeg_audio_codec(file_format),
        output_audio,
    ]
    run_ffmpeg_command(command, video_name=source_audio)
    return output_audio


def _transcode_audio(source_audio: str, output_audio: str, file_format: str) -> str:
    if Path(source_audio).suffix.lower() == _output_suffix(file_format):
        if source_audio != output_audio:
            Path(output_audio).parent.mkdir(parents=True, exist_ok=True)
            Path(output_audio).write_bytes(Path(source_audio).read_bytes())
        return output_audio

    command = [
        "ffmpeg",
        "-y",
        "-i",
        source_audio,
        "-c:a",
        _ffmpeg_audio_codec(file_format),
        output_audio,
    ]
    run_ffmpeg_command(command, video_name=source_audio)
    return output_audio


async def _notify_failure(voice_config: Volcovoice_VO, voice_id: str, error: Exception) -> None:
    if ENV == "local" or not post or "feishu_robot" not in my_config:
        return

    robot_req = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": f"{ENV} volcovoice service error",
                    "content": [
                        [
                            {"tag": "text", "text": f"error due to: {error}\n"},
                            {
                                "tag": "text",
                                "text": f"request body: {json.dumps(voice_config.model_dump(exclude_none=True), indent=2, ensure_ascii=False)}\n",
                            },
                        ]
                    ],
                }
            }
        },
    }
    if "error_at" in my_config:
        robot_req["content"]["post"]["zh_cn"]["content"][0].append(
            {"tag": "at", "user_id": f"{my_config['error_at']}"}
        )
    try:
        await post(my_config["feishu_robot"], robot_req, task_id=voice_id)
    except Exception as post_err:
        log.error(f"feishu notify failed: {post_err}")


async def process_volcovoice_task(voice_config: Volcovoice_VO) -> VolcovoiceResponse:
    async with volcovoice_semaphore:
        voice_id = str(voice_config.biz_id) if voice_config.biz_id else "unknown_biz"
        log.info(
            f"Processing volcovoice task: "
            f"{json.dumps(voice_config.model_dump(exclude_none=True), indent=2, ensure_ascii=False)}"
        )

        project_id = "volcovoice_" + str(random_with_system_time())
        output_prefix = os.path.join("./final", project_id)
        os.makedirs(output_prefix, exist_ok=True)
        start_ts = time.time()
        object_results: list[VolcovoiceObject] = []
        debug_objects: list[dict[str, Any]] = []

        if voice_config.voice_character not in character_options:
            raise ServiceException(code=450, message="unsupported volcovoice character")
        output_format = _normalize_output_format(voice_config.file_format)

        concurrency_sem = asyncio.Semaphore(15)

        async def process_single_text(idx: int, text: str) -> tuple[int, VolcovoiceObject, dict[str, Any]]:
            async with concurrency_sem:
                # Check if the text contains any pronounceable characters (Chinese, English letters, or numbers)
                is_pronounceable = False
                if text:
                    is_pronounceable = bool(re.search(r"[\u4e00-\u9fa5a-zA-Z0-9]", text))

                if not is_pronounceable:
                    log.info(f"Skipping Volcano TTS for non-pronounceable/empty text at index {idx}: {repr(text)}")
                    return idx, VolcovoiceObject(full_voice="", duration=0.0, detail_info=[]), {
                        "index": idx,
                        "text": text,
                        "segments": [],
                        "decisions": [],
                        "detail_info": [],
                    }

                raw_audio_output = os.path.join(output_prefix, f"volcovoice{idx}_{project_id}.{output_format}")
                raw_debug_json_path = os.path.join(output_prefix, f"volcovoice{idx}_{project_id}_raw.json")
                generate_result = await volcano_generate_voice(
                    character_options[voice_config.voice_character],
                    text,
                    raw_audio_output,
                    speed=voice_config.audio_speed_level,
                    volume=voice_config.volume / 100,
                    emotion=voice_config.emotion or "neutral",
                    emotion_active=voice_config.intensity is not None,
                    emotion_intensity=voice_config.intensity if voice_config.intensity is not None else 2.5,
                    debug_dump_path=raw_debug_json_path,
                    encoding=output_format,
                )

                working_audio = raw_audio_output
                if voice_config.volume == 0:
                    working_audio = await mute_audio(raw_audio_output, project_id)

                final_full_audio = os.path.join(output_prefix, f"volcovoice{idx}_{project_id}{_output_suffix(output_format)}")
                if output_format == "wav" or output_format == "mp3":
                    if working_audio != final_full_audio:
                        await asyncio.to_thread(_transcode_audio, working_audio, final_full_audio, output_format)
                    else:
                        final_full_audio = working_audio
                else:
                    await asyncio.to_thread(_transcode_audio, working_audio, final_full_audio, output_format)

                full_duration = (await asyncio.to_thread(get_audio_info, [final_full_audio]))[0]
                words = parse_frontend_words(generate_result.frontend_payloads)
                segments, decisions = _build_segments_from_words(words)

                segment_paths: list[str] = []
                if segments:
                    trim_tasks = []
                    for seg_idx, segment in enumerate(segments):
                        segment_name = _ensure_ascii_filename(f"seg_{idx}_{seg_idx}")
                        segment_path = os.path.join(output_prefix, f"{segment_name}_{project_id}{_output_suffix(output_format)}")
                        segment_paths.append(segment_path)
                        trim_tasks.append(
                            asyncio.to_thread(
                                _trim_audio_segment,
                                working_audio,
                                segment_path,
                                float(segment["start_ms"]),
                                float(segment["end_ms"]),
                                output_format,
                            )
                        )
                    await asyncio.gather(*trim_tasks)
                else:
                    segment_paths.append(final_full_audio)
                    segments = [
                        {
                            "caption_text": text,
                            "start_ms": 0.0,
                            "end_ms": full_duration * 1000.0,
                            "duration_ms": full_duration * 1000.0,
                            "pause_ms": 0.0,
                            "boundary_reason": "fallback_full_audio",
                            "word_count": 0,
                        }
                    ]
                    decisions = [{"decision": "fallback_full_audio"}]

                segment_durations = await asyncio.to_thread(get_audio_info, segment_paths)
                segment_urls = await asyncio.gather(*[upload_audio(path, project_id=project_id) for path in segment_paths])
                full_voice_url = await upload_audio(final_full_audio, project_id=project_id)

                detail_info: list[VolcovoiceDetail] = []
                for seg_idx, segment in enumerate(segments):
                    detail_info.append(
                        VolcovoiceDetail(
                            segment_url=segment_urls[seg_idx] if seg_idx < len(segment_urls) else "",
                            segment_duration=segment_durations[seg_idx] if seg_idx < len(segment_durations) else 0.0,
                            pause=round(float(segment["pause_ms"]) / 1000.0, 3),
                            caption_text=str(segment["caption_text"]),
                        )
                    )

                obj_res = VolcovoiceObject(
                    full_voice=full_voice_url,
                    duration=full_duration,
                    detail_info=detail_info,
                )
                debug_obj = {
                    "index": idx,
                    "text": text,
                    "full_voice_local_path": final_full_audio,
                    "full_voice_url": full_voice_url,
                    "full_duration": full_duration,
                    "raw_debug_json_path": raw_debug_json_path,
                    "frontend_words": [
                        {
                            "word": word.word,
                            "start_time": word.start_time,
                            "end_time": word.end_time,
                            "confidence": word.confidence,
                        }
                        for word in words
                    ],
                    "segments": segments,
                    "decisions": decisions,
                    "detail_info": [item.model_dump() for item in detail_info],
                }
                return idx, obj_res, debug_obj

        try:
            tasks = [process_single_text(idx, text) for idx, text in enumerate(voice_config.txt_str)]
            results = await asyncio.gather(*tasks)

            # Pre-allocate lists and insert in strict original index order
            object_results = [None] * len(voice_config.txt_str)
            debug_objects = [None] * len(voice_config.txt_str)
            for idx, obj_res, debug_obj in results:
                object_results[idx] = obj_res
                debug_objects[idx] = debug_obj

        except Exception as exc:
            log.opt(exception=True).error("volcovoice processing failed: {}", str(exc))
            await _notify_failure(voice_config, voice_id, exc)
            raise ServiceException(code=450, message=f"volcovoice generation failed: {exc}", data=str(exc))

        aggregate_debug_path = os.path.join(output_prefix, f"volcovoice_{project_id}_response.json")
        aggregate_debug_payload = {
            "request": voice_config.model_dump(exclude_none=True),
            "segmentation_rules": {
                "strong_punctuation": STRONG_PUNCTUATION,
                "comma_punctuation": COMMA_PUNCTUATION,
                "comma_soft_min_chars": COMMA_SOFT_MIN_CHARS,
                "comma_soft_min_duration_ms": COMMA_SOFT_MIN_DURATION_MS,
                "comma_soft_min_pause_ms": COMMA_SOFT_MIN_PAUSE_MS,
                "comma_hard_min_chars": COMMA_HARD_MIN_CHARS,
                "comma_hard_min_duration_ms": COMMA_HARD_MIN_DURATION_MS,
                "boundary_padding_ms": BOUNDARY_PADDING_MS,
            },
            "object_list": [item.model_dump() for item in object_results],
            "debug_objects": debug_objects,
        }
        _write_json(aggregate_debug_path, aggregate_debug_payload)
        debug_json_url = await upload_audio(aggregate_debug_path, project_id=project_id)

        final_path = output_prefix.replace("\\", "/")
        log.info(f"Delayed Delete: {final_path}")
        asyncio.create_task(delayed_delete(final_path, delay=50))

        log.info(f"{voice_id} finished, takes {time.time() - start_ts} seconds")
        return VolcovoiceResponse(
            biz_id=voice_config.biz_id or 0,
            object_list=object_results,
            volume=int(voice_config.volume),
            speech_rate=voice_config.audio_speed_level,
            voice_character=voice_config.voice_character,
            debug_json_url=debug_json_url,
        )


def _parse_debug_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a single Volcano voice request with the legacy websocket path.")
    parser.add_argument("--voice-character", default="Vivi", help="Display name from volcovoice character_options, or raw voice id.")
    parser.add_argument("--text", default="你好，这是一次火山引擎音频连通性测试。", help="Text to synthesize.")
    parser.add_argument("--output", default=r"C:\\tmp\\volcovoice_debug.wav", help="Output wav path.")
    parser.add_argument("--debug-json", default=r"C:\\tmp\\volcovoice_debug.json", help="Write the request/response debug payload to this JSON file.")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--volume", type=float, default=1.0)
    parser.add_argument("--emotion", default="neutral")
    parser.add_argument("--emotion-intensity", type=float, default=2.5)
    return parser.parse_args()


async def _debug_main() -> None:
    args = _parse_debug_args()
    voice_type = character_options.get(args.voice_character, args.voice_character)
    log.info(f"Debug volcovoice request with display_name={args.voice_character}, voice_type={voice_type}")
    await volcano_generate_voice(
        voice_type,
        args.text,
        args.output,
        speed=args.speed,
        volume=args.volume,
        emotion=args.emotion,
        emotion_active=False,
        emotion_intensity=args.emotion_intensity,
        debug_dump_path=args.debug_json,
    )
    log.info(f"Debug volcovoice request finished, output={args.output}")


if __name__ == "__main__":
    asyncio.run(_debug_main())
