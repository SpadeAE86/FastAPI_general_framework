import asyncio
import argparse
import json
import os
import time
from asyncio import Semaphore
from typing import List

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parents[1]))

from config.config import my_config, ENV
from exceptions.ServiceException import ServiceException
from models.pydantic_models.request.volcovoice_request import Volcovoice_VO, character_options
from models.pydantic_models.response.alivoice_response import AliVoiceResponse
from utils.ffmpeg_utils import mute_audio, concatenate_wavs, get_audio_info
from utils.general_utils import random_with_system_time, delayed_delete
from utils.log_utils import logger as log
from utils.obs_utils import upload_audio
from utils.volcano_utils import volcano_generate_voice

try:
    from utils.post_utils import post
except ImportError:
    post = None


volcovoice_semaphore = Semaphore(200)


async def process_volcovoice_task(voice_config: Volcovoice_VO) -> AliVoiceResponse:
    async with volcovoice_semaphore:
        voice_id = str(voice_config.biz_id) if voice_config.biz_id else "unknown_biz"
        log.info(
            f"Processing volcovoice task: "
            f"{json.dumps(voice_config.model_dump(exclude_none=True), indent=2, ensure_ascii=False)}"
        )

        project_id = "volcovoice_" + str(random_with_system_time())
        output_prefix = "/".join(["./final", project_id])
        audio_output_list: List[str] = []

        if voice_config.voice_character not in character_options:
            raise ServiceException(code=450, message="不支持的语音")

        tasks = []
        start_1 = time.time()

        async def sleep_and_yield(result=""):
            await asyncio.sleep(0)
            return result

        try:
            for idx, t in enumerate(voice_config.txt_str):
                output = "/".join([output_prefix, f"volcovoice{idx}_{project_id}.wav"]) if t else ""
                log.info(f"{idx}, {output}")
                os.makedirs(output_prefix, exist_ok=True)
                audio_output_list.append(output)

                if not t:
                    tasks.append(sleep_and_yield(""))
                else:
                    tasks.append(
                        volcano_generate_voice(
                            character_options[voice_config.voice_character],
                            t,
                            output,
                            speed=2 ** (voice_config.audio_speed_level / 500),
                            volume=voice_config.volume / 100,
                            emotion=voice_config.emotion or "neutral",
                            emotion_active=voice_config.intensity is not None,
                            emotion_intensity=voice_config.intensity if voice_config.intensity is not None else 2.5,
                        )
                    )
        except Exception as e:
            raise ServiceException(code=450, message=f"初始化语音服务失败: {e}", data=str(e))

        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            raise ServiceException(code=450, message=f"火山语音生成失败: {e}", data=str(e))

        if voice_config.volume == 0:
            mute_tasks = [mute_audio(audio, project_id) for audio in audio_output_list if audio]
            muted_results = await asyncio.gather(*mute_tasks)
            audio_output_list = [res for res in muted_results if res]
            log.info(f"完成静音: {audio_output_list}")

        log.info(f"{voice_id} finished, takes {time.time() - start_1} seconds")
        full_audio = ""
        valid_audios = [a for a in audio_output_list if a]
        if len(valid_audios) > 1:
            full_audio = await asyncio.to_thread(concatenate_wavs, valid_audios, project_id)
            log.info(f"full_audio: {full_audio}")

        audio_list = list(audio_output_list)
        if full_audio:
            audio_list.append(full_audio)

        try:
            durations = await asyncio.to_thread(get_audio_info, audio_list)
        except Exception as e:
            log.error(f"fatal error: {e}")
            if ENV != "local" and post and "feishu_robot" in my_config:
                robot_req = {
                    "msg_type": "post",
                    "content": {
                        "post": {
                            "zh_cn": {
                                "title": f"{ENV}环境火山tts服务报错",
                                "content": [
                                    [
                                        {"tag": "text", "text": f"error due to: {e}\n"},
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
                    log.error(f"飞书通知失败: {post_err}")
            raise e

        tasks2 = [upload_audio(a, project_id=project_id) for a in audio_output_list if a]
        if full_audio:
            tasks2.append(upload_audio(full_audio, project_id=project_id))

        obs_audio_list = await asyncio.gather(*tasks2)

        if valid_audios:
            final_path = os.path.join("./final", project_id).replace("\\", "/")
            log.info(f"Delayed Delete: {final_path}")
            asyncio.create_task(delayed_delete(final_path, delay=50))

        log.info(f"{voice_id}上传完成, 目前已经过 {time.time() - start_1} seconds")
        response = AliVoiceResponse(
            biz_id=voice_config.biz_id or 0,
            obs_audio_list=list(obs_audio_list),
            durations=durations,
            volume=int(voice_config.volume),
            speech_rate=2 ** (voice_config.audio_speed_level / 500),
            voice_character=voice_config.voice_character,
        )
        return response


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
