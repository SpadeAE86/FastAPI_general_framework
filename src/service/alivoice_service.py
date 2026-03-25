import asyncio
import json
import os
import random
import time
from math import log2
from asyncio import Semaphore
from typing import List

from config.config import my_config, audio_speech_rate, alivoice_options, male_voice, female_voice, emotion_voice, ENV
from exceptions.ServiceException import ServiceException
from models.pydantic_models.request.alivoice_request import Alivoice_VO
from models.pydantic_models.response.alivoice_response import AliVoiceResponse
from nls.token import getToken
from utils.alivoice_utils import AliTTS
from utils.ffmpeg_utils import mute_audio, concatenate_wavs, get_audio_info
from utils.general_utils import random_with_system_time, delayed_delete
from utils.log_utils import logger as log
from utils.obs_utils import upload_audio
try:
    from utils.post_utils import post
except ImportError:
    post = None

alivoice_semaphore = Semaphore(200)

async def process_alivoice_task(voice_config: Alivoice_VO) -> AliVoiceResponse:
    async with alivoice_semaphore:
        voice_id = str(voice_config.biz_id) if voice_config.biz_id else "unknown_biz"
        log.info(f"Processing alivoice task: {json.dumps(voice_config.model_dump(exclude_none=True), indent=2, ensure_ascii=False)}")
        
        token = getToken(my_config['audio']['Ali']['access_key_id'],
                         my_config['audio']['Ali']['access_key_secret'])
        project_id = "alivoice_" + str(random_with_system_time())
        output_prefix = "/".join(["./final", project_id])
        audio_output_list = []
        
        if voice_config.voice_character == "male":
            voice_config.voice_character = random.choice(male_voice)

        if voice_config.voice_character == "female":
            voice_config.voice_character = random.choice(female_voice)

        if voice_config.target_speech_rate and voice_config.voice_character in alivoice_options \
           and alivoice_options[voice_config.voice_character] in audio_speech_rate.keys():
            current_speech_rate = audio_speech_rate[alivoice_options[voice_config.voice_character]]
            adjustment_level = voice_config.target_speech_rate / current_speech_rate
            adjustment_level = 0.5 if adjustment_level < 0.5 else adjustment_level
            adjustment_level = 2 if adjustment_level > 2 else adjustment_level
            voice_config.audio_speed_level = int(log2(adjustment_level) * 500)

        tasks = []
        start_1 = time.time()
        
        async def sleep_and_yield(result=""):
            await asyncio.sleep(0)
            return result

        try:
            batch_size = 5
            stagger_delay = 1.0
            
            for i in range(0, len(voice_config.txt_str), batch_size):
                batch_tasks = []
                batch_texts = voice_config.txt_str[i:i+batch_size]
                
                for offset, t in enumerate(batch_texts):
                    idx = i + offset
                    output = "/".join([output_prefix, f"alitts{idx}_{project_id}.wav"]) if t else ""
                    log.info(f"{idx}, {output}")
                    os.makedirs(output_prefix, exist_ok=True)
                    name = "thread" + str(idx)
                    audio_output_list.append(output)

                    if not t:
                        batch_tasks.append(sleep_and_yield(""))
                    else:
                        if voice_config.voice_character in alivoice_options:
                            voice_service = AliTTS(name, output, alivoice_options[voice_config.voice_character],
                                                   voice_config.audio_speed_level, voice_config.volume, TOKEN=token)
                            if voice_config.voice_character in emotion_voice.keys():
                                category = voice_config.emotion
                                intensity = voice_config.intensity
                                t = f'<speak><emotion category="{category}" intensity="{intensity}">{t}</emotion></speak>'
                                log.info(f"{t}")
                            batch_tasks.append(voice_service.restful_request(t))
                        else:
                            log.info(f"{voice_config.voice_character} not supported")
                            raise ServiceException(code=450, message="不支持的语音")
                            
                # 执行本批次任务
                await asyncio.gather(*batch_tasks)
                
                # 若未处理完毕，则休眠错开时间
                if i + batch_size < len(voice_config.txt_str):
                    log.info(f"批次处理完成，等待 {stagger_delay}s 继续下一批...")
                    await asyncio.sleep(stagger_delay)

        except Exception as e:
            raise ServiceException(code=450, message=f"初始化语音服务失败: {e}", data=str(e))
        
        if voice_config.volume == 0:
            mute_tasks = [mute_audio(audio, project_id) for audio in audio_output_list if audio]
            muted_results = await asyncio.gather(*mute_tasks)
            # update audio_output_list filtering empty outputs
            audio_output_list = [res for res in muted_results if res]
            log.info(f"完成静音: {audio_output_list}")
            
        log.info(f"{voice_id} finished, takes {time.time() - start_1} seconds")
        full_audio = ""
        # filtering empty strings before concatenation
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
                robot_req = {"msg_type": "post", "content": {"post": {
                    "zh_cn": {
                        "title": f"{ENV}环境阿里云tts服务报错",
                        "content": [
                            [
                                {
                                    "tag": "text",
                                    "text": f"error due to: {e}\n"
                                },
                                {
                                    "tag": "text",
                                    "text": f"request body: {json.dumps(voice_config.model_dump(exclude_none=True), indent=2, ensure_ascii=False)}\n"
                                }
                            ]
                        ],
                    }
                }}}
                if "error_at" in my_config:
                    robot_req["content"]["post"]["zh_cn"]["content"][0].append({
                        "tag": "at",
                        "user_id": f"{my_config['error_at']}",
                    })
                try:
                    await post(my_config["feishu_robot"], robot_req, task_id=voice_id)
                except Exception as post_err:
                    log.error(f"飞书通知失败: {post_err}")
            raise e
            
        tasks2 = []
        for a in audio_output_list:
            if a: tasks2.append(upload_audio(a, project_id=project_id))
        if full_audio:
            tasks2.append(upload_audio(full_audio, project_id=project_id))

        obs_audio_list = await asyncio.gather(*tasks2)

        if valid_audios:
            final_path = os.path.join("./final", project_id).replace("\\", "/")
            log.info(f"Delayed Delete: {final_path}")
            asyncio.create_task(delayed_delete(final_path, delay=50))

        log.info(f"{voice_id}上传完成, 目前经过 {time.time()-start_1} seconds")
        response = AliVoiceResponse(
            biz_id=voice_config.biz_id or 0,
            obs_audio_list=list(obs_audio_list), 
            durations=durations,
            volume=int(voice_config.volume), 
            speech_rate=2 ** (voice_config.audio_speed_level/500), 
            voice_character=voice_config.voice_character
        )
        return response
