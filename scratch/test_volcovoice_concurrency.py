import sys
import os
import asyncio
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from models.pydantic_models.request.volcovoice_request import Volcovoice_VO
from service.volcovoice_service import process_volcovoice_task

async def main():
    print("Testing Volcano TTS Concurrency with process_volcovoice_task...")
    sentences = [
        "现在点小黄车就能拍，真的很划算。",
        "同级领先的大容量，冷饮随手可得！",
        "而且这是适配全品类创作工具的，非常好用。",
        "给孩子买的画材，弄脏桌子很不方便。",
        "大家都在使用这个新功能，你也快来试试吧。"
    ]

    request = Volcovoice_VO(
        biz_id=12345,
        user_id=67890,
        txt_str=sentences,
        voice_character="开朗青年",
        file_format="wav",
        audio_speed_level=1.0,
        volume=80,
    )

    start_time = time.time()
    try:
        response = await process_volcovoice_task(request)
        elapsed = time.time() - start_time
        print(f"Success! Elapsed time: {elapsed:.2f} seconds")
        print(f"Total objects returned: {len(response.object_list)}")
        
        for idx, obj in enumerate(response.object_list):
            print(f"Index {idx}: text='{sentences[idx]}', duration={obj.duration:.2f}s, url={obj.full_voice}")
            for d_idx, detail in enumerate(obj.detail_info):
                print(f"  Segment {d_idx}: text='{detail.caption_text}', duration={detail.segment_duration:.2f}s, url={detail.segment_url}")
    except Exception as e:
        print(f"Error during execution: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
